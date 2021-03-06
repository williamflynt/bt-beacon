import datetime
import logging
import os
from collections import deque
from functools import partialmethod
from random import randint

import numpy as np
import pynmea2
import serial
from pyubx import Manager

try:
    from utility import get_pn_uuid, UTC
except ImportError:
    from app.src.utility import get_pn_uuid, UTC

FILE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(FILE_DIR, "..", "..", "logs")
GPS_LOG = os.path.join(LOG_DIR, 'gps.log')

logger = logging.getLogger('gps')
logfile = logging.FileHandler(GPS_LOG)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s:: %(message)s')
logfile.setFormatter(formatter)
logger.addHandler(logfile)


class CoordinateService(Manager):
    def __init__(self, ser, debug=False, maxlen_vel=11, vel_avg_seconds=10,
                 vel_inst_seconds=10, s_i_max=55, s_a_max=55, t_i_max=30,
                 t_a_max=12.5, ref_spd=40, ref_spd_mod=20, gen_fake_vel=False):
        if not debug:
            logger.setLevel(logging.INFO)
        else:
            logger.setLevel(logging.DEBUG)

        logger.info("Beginning GPS service setup...")
        try:
            logger.info("Setting up serial connection to GPS device...")
            if isinstance(ser, bytes) or isinstance(ser, str):
                ser = serial.Serial(ser)
        except Exception:
            logger.exception("\n"
                             "********************\n"
                             "**GPS device error**\n"
                             "********************")
            raise

        logger.info("Setting up PyUBX Manager...")
        Manager.__init__(self, ser, debug)
        self._dumpNMEA = False
        self.latest_fix = None
        self.latest_vel = None
        self.msg_alarm = 0
        logger.info("Manager set up. Initializing variables...")

        self.gen_fake_vel = gen_fake_vel

        # Initialize values for velocity checking
        # we need enough values to satisfy average requirements - assume 1/sec
        maxlen_vel = max(maxlen_vel, vel_avg_seconds + 1)
        self.vel_array = deque(maxlen=maxlen_vel)  # velocity = (speed, track)
        self.vel_avg_seconds = vel_avg_seconds  # how long to consider in avgs
        self.vel_inst_seconds = vel_inst_seconds  # time ago to calc inst diff

        # Initialize parameters against which to check velocity
        self.s_i_max = s_i_max  # speed-instant trigger
        self.s_a_max = s_a_max  # speed-average trigger
        self.t_i_max = t_i_max  # track-instant trigger
        # We compare sine values - so compute this now
        # It's the max difference in sine value vs angular value
        self.t_a_max = 7  # init greater than sine is possible
        self.set_tamax(t_a_max)  # track-average trigger
        self.spd_holder = 0.0  # init outside func for use in comparison
        # Used to calculate a dynamic t_i_max based on speed
        self.ref_spd = ref_spd  # Speed to start decreasing t_i_max
        self.ref_spd_mod = ref_spd_mod  # Used to tune t_i_max descent

        logger.info("GPS service initialized.")

    @staticmethod
    def hdg_diff(init, final):
        if init > 360 or init < 0 or final > 360 or final < 0:
            raise Exception("out of range. init: {} // final: {}".format(init, final))
        diff = final - init
        abs_diff = abs(diff)

        if abs_diff == 180:
            return abs_diff
        elif abs_diff < 180:
            return diff
        elif final > init:
            return abs_diff - 360
        else:
            return 360 - abs_diff

    @staticmethod
    def _vel_proc(vel_dict, v_or_k, index, funcname):
        """
        :param v_or_k: str Either 'keys' or 'values' - what do we want?
        :param index: int The index of the key/value we want (typically 0 or 1)
        :param vel_dict: dict The velocity dict: { timestamp: ( speed, track ) }
        :return: float The requested value
        """
        # Check errors / log
        if not isinstance(vel_dict, dict):
            logger.error("***{} was passed a non-dict parameter") \
                .format(funcname)
            return -1
        if v_or_k not in ["values", "keys"]:
            logger.error("***{} was passed {}, not 'keys' or 'values'") \
                .format(funcname, v_or_k)
            return -1
        # Do actual work
        try:
            if v_or_k == "keys":
                return list(getattr(vel_dict, v_or_k)())[index]
            else:
                return list(getattr(vel_dict, v_or_k)())[0][index]
        except KeyError:
            logger.error("***{} encountered KeyError for {}" \
                         .format(funcname, vel_dict))
            return -1

    _spd = partialmethod(_vel_proc, v_or_k="values", index=0, funcname="_spd")
    _trk = partialmethod(_vel_proc, v_or_k="values", index=1, funcname="_trk")
    _ts = partialmethod(_vel_proc, v_or_k="keys", index=0, funcname="_ts")

    @staticmethod
    def avg_sin(angles):
        """
        Given a list of angles in degrees, return the average of the
          individual sine values.
        :param angles: list A list of angles in degrees
        :return: float Average sine value for the list
        """
        avg = sum(np.sin(np.radians(angles))) / len(angles)
        return round(avg, 4)

    def set_tamax(self, new_max):  # Alternative is self.t_a_max as property
        try:
            self.t_a_max = np.sin(np.radians(new_max))
        except Exception:
            logger.error("*****Error computing new t_a_max for value {}"
                         .format(new_max))

    def _check_velocity(self):
        try:
            now = list(self.vel_array[0])[0]  # Get first key (timestamp)
        except IndexError:
            return

        def speed_alarm():
            s_val = self._spd(self.vel_array[0])  # { now: (speed, track) }
            self.spd_holder = s_val
            """
            This gets the least-recent speed adhering to the vel_inst_seconds.
            The idea is to check less recently than the fastest rate of msgs.
            It will be the same for track (below).
            """
            s_i_check_val = [self._spd(x) for x in self.vel_array if
                             self._ts(x) >= (now - self.vel_inst_seconds)][-1]
            s_a_check_list = [self._spd(x) for x in self.vel_array if
                              self._ts(x) >= (now - self.vel_avg_seconds)]
            s_a_check_val = sum(s_a_check_list) / len(s_a_check_list)
            alarm = (abs(s_val - s_i_check_val) > self.s_i_max or
                     abs(s_val - s_a_check_val) > self.s_a_max)
            return alarm

        def track_alarm():
            # Reduce allowable instant track variance with increasing speed
            try:
                if self.spd_holder >= self.ref_spd:
                    current_t_i_max = min([
                        self.t_i_max,
                        (self.ref_spd/(self.spd_holder + self.ref_spd_mod)) * self.t_i_max
                    ])
                else:
                    current_t_i_max = self.t_i_max
            except:
                current_t_i_max = self.t_i_max
                logger.exception("***Error calculating speed-dependent t_i_max")

            t_val = self._trk(self.vel_array[0])  # { now: (speed, track) }
            t_i_check_val = [self._trk(x) for x in self.vel_array if
                             self._ts(x) >= (now - self.vel_inst_seconds)][-1]
            # Compute average heading over time
            t_a_check_val = self.avg_sin([self._trk(x) for x in self.vel_array if
                                          self._ts(x) >= (now - self.vel_avg_seconds)])
            alarm = (self.hdg_diff(t_val, t_i_check_val) > current_t_i_max or
                     abs(np.sin(np.radians(t_val)) - t_a_check_val) > self.t_a_max)
            return alarm

        try:
            # speed at rest 0-2.5
            if speed_alarm() or (self.spd_holder > 2.5 and track_alarm()):
                try:
                    self.msg_alarm = 1
                    self.latest_vel = self._constr_vel()
                    self.vel_array.clear()
                except:
                    logger.exception("***Error getting velocity alarms")
        except KeyError:
            logger.exception("\n"
                             "********************\n"
                             "***velocity error***\n"
                             "********************")
        except Exception:
            logger.exception("\n"
                             "********************\n"
                             "***velocity error***\n"
                             "********************")

    # Override onNMEA from parent class to do work
    def onNMEA(self, buffer):
        msg = pynmea2.parse(buffer)
        if msg.__class__ is pynmea2.GGA:  # position msg
            if msg.gps_qual > 0:
                self.latest_fix = msg
        elif msg.__class__ is pynmea2.VTG:  # velocity msg
            try:
                speed = msg.spd_over_grnd_kmph
                track = msg.true_track
                if self.gen_fake_vel:  # To test other stuff
                    speed = 50 + randint(-25, 25)
                    track = 180 + randint(-35, 35)
                if speed and track:
                    # now = timestamp in seconds
                    now = datetime.datetime.timestamp(datetime.datetime.now(tz=UTC))
                    self.vel_array.appendleft({now: (speed, track)})
                    self._check_velocity()
            except AttributeError:
                logger.exception("***Bad properties for VTG Sentence***")
        else:
            # Potential to expand to more message types here
            pass

    def get_latest_fix(self):
        if self.latest_fix is not None:
            return (
                self.latest_fix.latitude,
                self.latest_fix.longitude,
                self.latest_fix.altitude,
                self.latest_fix.timestamp
            )
        else:
            return 0

    def get_latest_velocity(self):
        if self.latest_vel is not None:
            return self.latest_vel
        else:
            return 0

    def _constr_vel(self):
        try:
            for k, v in self.vel_array[0].items():
                return (
                    v[0], v[1],  # speed in kph, track direction (true)
                    datetime.datetime.fromtimestamp(k, tz=UTC)  # Python DT obj
                )
        except IndexError:
            return 0
        except Exception:
            logger.exception("\n"
                             "********************\n"
                             "**constr_vel error**\n"
                             "********************")
            return 0
