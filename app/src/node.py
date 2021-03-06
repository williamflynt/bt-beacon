import datetime
import json
import logging
import os
import threading
import time
import uuid
from timeit import default_timer as timer

from pubnub.enums import PNStatusCategory
from pubnub.pnconfiguration import PNConfiguration
from pubnub.pubnub import PubNub

try:
    import gps
    import scan
    from utility import get_pn_uuid, UTC, sloppy_smaller
except ImportError:
    import app.src.gps as gps
    import app.src.scan as scan
    from app.src.utility import get_pn_uuid, UTC, sloppy_smaller

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

logger = logging.getLogger('node')
logfile = logging.FileHandler(NODE_LOG)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s:: %(message)s')
logfile.setFormatter(formatter)
logger.addHandler(logfile)


class Node(threading.Thread):
    def __init__(self, gps_device, pub_key=None, sub_key=None, interval=300, debug=False):
        if not debug:
            logger.setLevel(logging.INFO)
        else:
            logger.setLevel(logging.DEBUG)
        logger.info("***Setting up Node")

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

        logger.info("Setting up BLE scanning service")
        self.scan_svc = scan.BleMonitor(debug=debug)
        self.scan_svc.daemon = True

        logger.info("Node initialized - ready for start")

    def _publish_callback(self, result, status):
        if not status.is_error():
            # Successful publish event - set for local message deletion
            self.scan_svc.reset_in_view(
                status_to_remove="retrieved",
                new_status='published'
            )
        elif status.category == PNStatusCategory.PNAccessDeniedCategory:
            # Store message
            logger.warning("Publish failed with PNAccessDenied")
        elif status.category == PNStatusCategory.PNBadRequestCategory:
            # Maybe bad keys, or an SDK error
            logger.warning("Publish failed with PNABadRequestCategory")
        elif status.category == PNStatusCategory.PNTimeoutCategory:
            # Store message and retry later
            logger.warning("Publish failed with PNTimeoutCategory")

    def _log_and_publish(self, log=True):
        logging.debug("Publishing a message...")

        # Get these ASAP to make old message detection more accurate
        location = self.gps_svc.get_latest_fix()
        velocity = self.gps_svc.get_latest_velocity()

        now = datetime.datetime.now(tz=UTC)
        if not self.expected:
            self.expected = now + datetime.timedelta(seconds=30)

        msg_id = str(uuid.uuid1())
        msgs = self.scan_svc.retrieve_in_view(reset=True,
                                              set_status='retrieved')

        logging.debug("--setting msg vars")
        if location:
            location = list(location)
            is_old_location = int(sloppy_smaller(location[3], self.expected) or
                                  location == self.last_loc)
            self.last_loc = location
            location[3] = location[3].isoformat()  # %H:%M:%S
        else:
            is_old_location = 0

        if velocity:  # velocity contains a full datetime
            velocity = list(velocity)
            is_old_velocity = int(sloppy_smaller(velocity[2], self.expected) or
                                  velocity == self.last_vel)
            self.last_vel = velocity
            velocity[2] = velocity[2].time().strftime('%H:%M:%S')  # Trim microseconds
        else:
            is_old_velocity = 0

        self.expected = now + \
                        datetime.timedelta(seconds=self.interval) + \
                        datetime.timedelta(seconds=2)

        logging.debug("--contructing")
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

            if log:
                with open(MSG_LOG, 'a') as msg_log:
                    msg_log.writelines([json.dumps(main_msg), "\n"])

        except Exception:
            logger.exception("\n"
                             "********************\n"
                             "***main_msg error***\n"
                             "********************")
            main_msg = None

        logging.debug("--pushing")
        if not self.debug and self.pubnub and main_msg:
            self.pubnub.publish() \
                .channel('node_raw') \
                .message(main_msg) \
                .should_store(True) \
                .meta({"msg_id": msg_id}) \
                .pn_async(self._publish_callback)
        else:
            logger.debug(("OFFLINE MSG", {
                "gps": self.gps_svc.get_latest_fix(),
                "vel": self.gps_svc.get_latest_velocity(),
                "in_view": {"msg_count": sum([len(v) for k, v in msgs.items()]),
                            "device_count": len(msgs.keys())},
            }))
        logging.debug("--published.")

    def run(self):
        # First we start our supporting threads
        logger.info("Starting GPS service")
        self.gps_svc.start()
        # Get node coordinates for the scan service as needed here
        logger.info("Getting the first GPS fix")

        timeout = 10
        clock = timer()
        while True:  # Wait for fix w/ a max timeout
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

        """old_mod and new_mod get compared. Every X seconds (where X is
        the interval) we will notice the new_mod fall below the
        old_mod (ie: we passed another factor of interval). That's
        when we should fire the message off! This method is nice
        because it doesn't wander over time like threading.Timer or
        a simple implementation of time.sleep."""
        old_mod = 0.0
        while self.switch:
            elapsed = timer() - clock
            new_mod = elapsed % self.interval
            if new_mod < old_mod and not self.msg_alarm:
                self.msg_alarm = 1
            old_mod = new_mod

            if (self.msg_alarm or
                self.gps_svc.msg_alarm or
                self.scan_svc.msg_alarm) and elapsed >= 1:  # max of ~1 msg/sec
                self._log_and_publish()
                # reset for a fresh check - do it first to let clock build
                # messages come at various times; reset now vs. at mod check
                clock = timer()
                self.msg_alarm = 0
                self.gps_svc.msg_alarm = 0
                self.scan_svc.msg_alarm = 0
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
