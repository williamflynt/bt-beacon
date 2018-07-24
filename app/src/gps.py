import datetime
from cmath import rect, phase
from collections import deque
from math import radians, degrees

import pynmea2
from pyubx import Manager


class CoordinateService(Manager):
    def __init__(self, ser, debug=False, maxlen_vel=11, vel_avg_seconds=10,
                 vel_inst_seconds=10, s_i_max=16.1, s_a_max=16.1,
                 t_i_max=15, t_a_max=30):
        if isinstance(ser, bytes) or isinstance(ser, str):
            import serial
            ser = serial.Serial(ser)
        Manager.__init__(self, ser, debug)
        self._dumpNMEA = False
        self.latest_fix = None
        self.parent = None

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
        self.t_a_max = t_a_max  # track-average trigger

    @staticmethod
    def hdg_diff(init, final):
        if init > 360 or init < 0 or final > 360 or final < 0:
            raise Exception("out of range")
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
    def mean_angle(deg):
        return degrees(phase(sum(rect(1, radians(d)) for d in deg) / len(deg)))

    def _check_velocity(self):
        try:
            now = list(self.vel_array[0])[0]  # Get first key (timestamp)
        except IndexError:
            return

        # Check speed for instant diff and average diff
        def speed_alarm():
            s_val = self.vel_array[0][0]
            """
            This gets the least-recent speed adhering to the vel_inst_seconds.
            The idea is to check less recently than the fastest rate of msgs.
            It will be the same for track (below).
            """
            s_i_check_val = [x[0] for x in self.vel_array if
                             list(x.keys)[0] >= (now - self.vel_inst_seconds)][-1]
            s_a_check_list = [x[0] for x in self.vel_array if
                              list(x.keys)[0] >= (now - self.vel_avg_seconds)]
            s_a_check_val = sum(s_a_check_list) / len(s_a_check_list)
            return (abs(s_val - s_i_check_val) > self.s_i_max or
                    abs(s_val - s_a_check_val) > self.s_a_max)

        # Check speed for instant diff and average diff
        def track_alarm():
            t_val = abs(self.vel_array[0][1])
            t_i_check_val = [x[1] for x in self.vel_array if
                             list(x.keys)[0] >= (now - self.vel_inst_seconds)][-1]
            # Compute average heading over time
            t_a_check_val = self.mean_angle(
                [x[1] for x in self.vel_array if
                 list(x.keys)[0] >= (now - self.vel_avg_seconds)]
            )
            return (self.hdg_diff(t_val, t_i_check_val) > self.t_i_max or
                    self.hdg_diff(t_val, t_a_check_val) > self.t_a_max)

        if speed_alarm() or track_alarm():
            try:
                self.parent.msg_alarm = 1
            except AttributeError:
                # Probably running this standalone
                pass

    # Override onNMEA from parent class to do work
    def onNMEA(self, buffer):
        msg = pynmea2.parse(buffer)
        if msg.__class__ is pynmea2.GGA:  # position msg
            if msg.gps_qual > 0:
                self.latest_fix = msg
        elif msg.__class__ is pynmea2.VTG:  # velocity msg
            speed = msg.spd_over_grnd_kmph
            track = msg.true_track
            if speed and track:
                # now = timestamp in seconds
                now = datetime.datetime.timestamp(datetime.datetime.now())
                self.vel_array.appendleft({now: (speed, track)})
                self._check_velocity()
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
        try:
            for k, v in self.vel_array[0].items():
                return (
                    v[0], v[1],
                    datetime.datetime.fromtimestamp(k)
                )
        except IndexError:
            return 0
