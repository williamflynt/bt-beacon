import datetime
import json
import logging
import os
import threading
from threading import current_thread
import time
import uuid

from timeit import default_timer as timer

from pubnub.enums import PNStatusCategory
from pubnub.pnconfiguration import PNConfiguration
from pubnub.pubnub import PubNub

try:
    import app.src.gps as gps
    import app.src.scan as scan
except ImportError as e:
    import gps
    import scan

# ScanService needs a node name to publish and configure via PubNub.
# Let's use a UUID for the device.
NODE = uuid.getnode()

# The ScanService needs coordinates in meters from an origin to trilaterate.
# Since this Node class is concerned with true coordinates, we can just set
#   0, 0 until we refactor ScanService to use something else.
NODE_COORDS = (0, 0)

MSG_LOG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'msg_log_{}'.format(datetime.datetime.now().strftime("%Y%m%d_%H%M"))
)


class Node(threading.Thread):
    def __init__(self, gps_device, pub_key=None, sub_key=None, interval=30, debug=False):
        self.parent = current_thread()
        threading.Thread.__init__(self)
        self.daemon = False

        # Set up logging to file if debug is False
        if not debug:
            logging.basicConfig(filename='node.log', level=logging.INFO)
        else:
            logging.basicConfig(level=logging.DEBUG)

        self.interval = max(interval, 1)  # min msg interval of 1 second

        self.expected = None  # track expected message times
        self.last_loc = None  # last fix message for comparison
        self.last_vel = None  # last velocity message for comparison
        self.tz = datetime.timezone(datetime.timedelta(0))

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
        logging.info("Connecting to PubNub")
        pnconfig = PNConfiguration()
        pnconfig.subscribe_key = sub_key
        pnconfig.publish_key = pub_key
        pnconfig.ssl = False
        try:
            self.pubnub = PubNub(pnconfig)
            logging.info("Connected with SSL set to {}".format(pnconfig.ssl))
        except:
            self.pubnub = None
            logging.warning("No PubNub connection. Running offline-only mode.")

        logging.info("Setting up GPS service")
        self.gps_svc = gps.CoordinateService(gps_device)
        self.gps_svc.daemon = True
        self.gps_svc.parent = current_thread()

        logging.info("Setting up BLE scanning service")
        self.scan_svc = scan.BleMonitor()
        self.scan_svc.daemon = True
        self.scan_svc.parent = current_thread()

        logging.info("Node initialized - ready for start")

    def _publish_callback(self, result, status):
        if not status.is_error():
            # Successful publish event - set for local message deletion
            self.scan_svc.reset_in_view(
                status_to_remove="retrieved",
                new_status='published'
            )
        elif status.category == PNStatusCategory.PNAccessDeniedCategory:
            # RESTART BOTTLE FOR CONFIG IF STOPPED
            # Store message
            pass
        elif status.category == PNStatusCategory.PNBadRequestCategory:
            # Maybe bad keys, or an SDK error
            # Store message
            pass
        elif status.category == PNStatusCategory.PNTimeoutCategory:
            # Store message and retry later
            pass

    def _log_and_publish(self, log=True):

        now = datetime.datetime.now()
        if not self.expected:
            self.expected = now
        else:
            # The latest expected message is the last one, plus our set interval
            self.expected = self.expected + datetime.timedelta(seconds=self.interval)

        msg_id = str(uuid.uuid1())
        # TODO: We would like to set a UUID-type status here but...
        # the data in the message/meta/etc isn't accessible to
        # our _publish_callback method (at least that I can find).
        msgs = self.scan_svc.retrieve_in_view(reset=True,
                                              set_status='retrieved')

        location = self.gps_svc.get_latest_fix()
        if location:
            location = list(location)
            is_old_location = int(location[3] > self.expected.time() and
                                  location != self.last_loc)
            location[3] = location[3].isoformat()
            self.last_loc = location
        else:
            is_old_location = 0

        velocity = self.gps_svc.get_latest_velocity()
        if velocity:
            velocity = list(velocity)
            is_old_velocity = int(velocity[3] > self.expected and
                                  velocity != self.last_vel)
            velocity[3] = velocity[3].time().isoformat()
            self.last_vel = velocity
        else:
            is_old_velocity = 0

        main_msg = {
            "device_uid": NODE,
            "message_uid": msg_id,
            "timestamp": datetime.datetime.now(tz=self.tz).isoformat(),
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

        if not self.debug and self.pubnub:
            p = self.pubnub.publish() \
                .channel('node_raw') \
                .message(main_msg) \
                .should_store(True) \
                .meta({"msg_id": msg_id}) \
                .async(self._publish_callback)
        else:
            logging.debug(("OFFLINE MSG", {
                "gps": self.gps_svc.get_latest_fix(),
                "in_view": {"msg_count": sum([len(v) for k, v in msgs.items()]),
                            "device_count": len(msgs.keys())},
            }))

    def run(self):
        # First we start our supporting threads
        logging.info("Starting GPS service")
        self.gps_svc.start()
        # Get node coordinates for the scan service as needed here
        logging.info("Getting the first GPS fix")
        # # Wait for fix or a set of fixes w/ a max timeout
        timeout = 10
        clock = timer()
        while True:
            time.sleep(0.5)
            if timer() - clock > timeout:
                logging.info("GPS fix timeout - moving on")
                break
            elif self.gps_svc.latest_fix:
                logging.info("GPS fix acquired")
                break

        logging.info("Starting BLE scanner")
        self.scan_svc.start()
        logging.info("BLE scanner started")

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
        logging.info("Shutting down GPS service")
        self.gps_svc.shutdown()
        logging.info("Shutting down BLE scanner")
        self.scan_svc.terminate()
        logging.info("Shutting down node")
        self.switch = False
        self.join(3.0)
        logging.info("done")
