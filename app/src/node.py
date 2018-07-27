import datetime
import json
import logging
import os
import threading
import time
import uuid
from threading import current_thread
from timeit import default_timer as timer

import pytz
from pubnub.enums import PNStatusCategory
from pubnub.pnconfiguration import PNConfiguration
from pubnub.pubnub import PubNub

try:
    import gps
    import scan
    from utility import get_pn_uuid
except ImportError:
    import app.src.gps as gps
    import app.src.scan as scan
    from app.src.utility import get_pn_uuid

# ScanService needs a node name to publish and configure via PubNub.
# Let's use a UUID for the device.
NODE = get_pn_uuid()

# The ScanService needs coordinates in meters from an origin to trilaterate.
# Since this Node class is concerned with true coordinates, we can just set
#   0, 0 until we refactor ScanService to use something else.
NODE_COORDS = (0, 0)

FILE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(FILE_DIR, "..", "..", "logs")
STR_DATE = datetime.datetime.now().strftime("%y%m%d_%H%M")
MSG_LOG = os.path.join(LOG_DIR, 'messages-{}.log'.format(STR_DATE))
NODE_LOG = os.path.join(LOG_DIR, "node.log")

# We work in UTC
UTC = pytz.timezone('UTC')

logging.basicConfig(filename=os.path.join(LOG_DIR,
                                          'debug.log'),
                    level=logging.DEBUG)
logger = logging.getLogger('node')
logfile = logging.FileHandler(NODE_LOG)
logger.addHandler(logfile)


class Node(threading.Thread):
    def __init__(self, gps_device, pub_key=None, sub_key=None, interval=300, debug=False):
        if not debug:
            logger.setLevel(logging.INFO)
            logfile.setLevel(logging.INFO)
        else:
            logger.setLevel(logging.DEBUG)
            logfile.setLevel(logging.DEBUG)

        self.parent = current_thread()

        threading.Thread.__init__(self)
        self.daemon = False

        self.interval = max(interval, 1)  # min msg interval of 1 second

        self.expected = None  # track expected message times
        self.last_loc = None  # last fix message for comparison
        self.last_vel = None  # last velocity message for comparison

        self.debug = debug
        if self.debug:
            print("Writing to {}".format(MSG_LOG))
            print("*** Debug messages are not complete messages.")

        self.switch = True
        self.msg_alarm = 0

        # This is the alternative to keeping secrets on the Pi
        while pub_key is None or sub_key is None:
            if pub_key is None:
                while True:
                    p1 = input("Enter your publishing key: ")
                    if len(p1) != 42 and p1 != "demo":
                        print("Your publishing key is too short!")
                    else:
                        pub_key = p1
                        break
            if sub_key is None:
                while True:
                    s1 = input("Enter your subscription key: ")
                    if len(s1) != 42 and s1 != "demo":
                        print("Your subscription key is too short!")
                    else:
                        sub_key = s1
                        break

        # Set up PubNub for publishing stream data
        # In the future we would outsource our publishing to separate layer
        logger.info("Connecting to PubNub")
        pnconfig = PNConfiguration()
        pnconfig.subscribe_key = sub_key
        pnconfig.publish_key = pub_key
        pnconfig.uuid = NODE
        pnconfig.ssl = False
        try:
            self.pubnub = PubNub(pnconfig)
            logger.info("Connected with SSL set to {}".format(pnconfig.ssl))
        except Exception:
            self.pubnub = None
            logger.warning("No PubNub connection. Running offline-only mode.")

        logger.info("Setting up GPS service")
        self.gps_svc = gps.CoordinateService(gps_device, debug=debug)
        self.gps_svc.daemon = True
        self.gps_svc.parent = current_thread()

        logger.info("Setting up BLE scanning service")
        self.scan_svc = scan.BleMonitor(debug=debug)
        self.scan_svc.daemon = True
        self.scan_svc.parent = current_thread()

        logger.info("Node initialized - ready for start")

    def _publish_callback(self, result, status):
        if not status.is_error():
            # Successful publish event - set for local message deletion
            self.scan_svc.reset_in_view(
                status_to_remove="retrieved",
                new_status='published'
            )
            logging.debug("Publish success")
        elif status.category == PNStatusCategory.PNAccessDeniedCategory:
            # RESTART BOTTLE FOR CONFIG IF STOPPED
            # Store message
            logger.warning("Publish failed with PNAccessDenied")
        elif status.category == PNStatusCategory.PNBadRequestCategory:
            # Maybe bad keys, or an SDK error
            import pickle
            pickle_path = os.path.join(FILE_DIR, "status.p")
            with open(pickle_path, "wb") as pfile:
                pickle.dump(status, pfile)
            logger.warning("Publish failed with PNABadRequestCategory. Load status object from {}".format(pickle_path))
        elif status.category == PNStatusCategory.PNTimeoutCategory:
            # Store message and retry later
            logger.warning("Publish failed with PNTimeoutCategory")

    def _log_and_publish(self, log=True):
        # Get these ASAP to make old message detection more accurate
        location = self.gps_svc.get_latest_fix()
        velocity = self.gps_svc.get_latest_velocity()

        now = datetime.datetime.now(UTC)
        if not self.expected:
            self.expected = now + datetime.timedelta(seconds=1)

        msg_id = str(uuid.uuid1())
        # TODO: We would like to set a UUID-type status here but...
        # the data in the message/meta/etc isn't accessible to
        # our _publish_callback method (at least that I can find).
        msgs = self.scan_svc.retrieve_in_view(reset=True,
                                              set_status='retrieved')

        if location:
            location = list(location)
            logging.debug("Loc Old Test: {} (passed)  versus {} (expected)".format(location[3], self.expected.time()))
            is_old_location = int(location[3] > self.expected.time() or
                                  location == self.last_loc)
            logging.debug("Result: {}".format(is_old_location))
            location[3] = location[3].isoformat()  # %H:%M:%S
            self.last_loc = location
        else:
            is_old_location = 0

        if velocity:
            velocity = list(velocity)
            logging.debug("Vel Old Test: {} (passed)  versus {} (expected)".format(velocity[2], self.expected.time()))
            is_old_velocity = int(velocity[2] > self.expected or
                                  velocity == self.last_vel)
            logging.debug("Result: {}".format(is_old_velocity))
            velocity[2] = velocity[2].time().isoformat()  # %H:%M:%S
            self.last_vel = velocity
        else:
            is_old_velocity = 0

        self.expected = now + \
                        datetime.timedelta(seconds=self.interval) + \
                        datetime.timedelta(seconds=2)

        try:
            main_msg = {
                "device_uid": NODE,
                "message_uid": msg_id,
                "timestamp": datetime.datetime.now(tz=UTC).isoformat(),
                "location": location,
                "is_old_location": is_old_location,
                "velocity": velocity,
                "is_old_velocity": is_old_velocity,
                "in_view": {"msg_count": sum([len(v) for k, v in msgs.items()]),
                            "devices": list(msgs.keys()),
                            "raw": msgs},
                "tlm": {},
            }
        except Exception:
            logger.exception("********************\n"
                             "***main_msg error***\n"
                             "********************")
            main_msg = None

        if log and main_msg:
            with open(MSG_LOG, 'a') as msg_log:
                msg_log.writelines([json.dumps(main_msg), "\n"])

        if not self.debug and self.pubnub and main_msg:
            self.pubnub.publish() \
                .channel('node_raw') \
                .message(main_msg) \
                .should_store(True) \
                .meta({"msg_id": msg_id}) \
                .async(self._publish_callback)
        else:
            logger.debug(("OFFLINE MSG", {
                "gps": self.gps_svc.get_latest_fix(),
                "vel": self.gps_svc.get_latest_velocity(),
                "in_view": {"msg_count": sum([len(v) for k, v in msgs.items()]),
                            "device_count": len(msgs.keys())},
            }))

    def run(self):
        # First we start our supporting threads
        logger.info("Starting GPS service")
        self.gps_svc.start()
        # Get node coordinates for the scan service as needed here
        logger.info("Getting the first GPS fix")
        # # Wait for fix or a set of fixes w/ a max timeout
        timeout = 10
        clock = timer()
        while True:
            time.sleep(0.5)
            if timer() - clock > timeout:
                logger.info("GPS fix timeout - moving on")
                break
            elif self.gps_svc.latest_fix:
                logger.info("GPS fix acquired")
                break

        logger.info("Starting BLE scanner")
        self.scan_svc.start()
        logger.info("BLE scanner started")

        clock = timer()  # Start a clock and publish a message on a timer
        self.msg_alarm = 1  # Set to 1 to start with a message

        # old_mod and new_mod get compared. Every X seconds (where X is
        #   the interval) we will notice the new_mod fall below the
        #   old_mod (ie: we passed another factor of interval). That's
        #   when we should fire the message off! This method is nice
        #   because it doesn't wander over time like threading.Timer or
        #   a simple implementation of time.sleep.
        old_mod = 0.0
        while self.switch:
            elapsed = timer() - clock
            new_mod = elapsed % self.interval
            if new_mod < old_mod and not self.msg_alarm:
                self.msg_alarm = 1
            old_mod = new_mod

            if self.msg_alarm and elapsed >= 1:  # max of ~1 msg/sec
                # reset for a fresh check - do it first to let clock build
                # messages come at various times; reset now vs. at mod check
                clock = timer()
                self.msg_alarm = 0
                self._log_and_publish()
                old_mod = 0.0  # reset at latest possible

            time.sleep(0.1)

    def terminate(self):
        logger.info("Shutting down GPS service")
        self.gps_svc.shutdown()
        logger.info("Shutting down BLE scanner")
        self.scan_svc.terminate()
        logger.info("Shutting down node")
        self.switch = False
        self.join(3.0)
        logger.info("done")
