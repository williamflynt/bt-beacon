import datetime
import logging
import threading
import time
import uuid

from timeit import default_timer as timer

from pubnub.enums import PNStatusCategory
from pubnub.pnconfiguration import PNConfiguration
from pubnub.pubnub import PubNub

try:
    import app.src.gps as gps
    import app.src.scan as scan
except ModuleNotFoundError as e:
    import gps
    import scan

# ScanService needs a node name to publish and configure via PubNub.
# Let's use a UUID for the device.
NODE = uuid.getnode()
# The ScanService needs coordinates in meters from an origin to trilaterate.
#
# Since this Node class is concerned with true coordinates, we can just set
#   0, 0 until we refactor ScanService to use something else.
NODE_COORDS = (0, 0)


class Node(threading.Thread):
    def __init__(self, gps_device, pub_key=None, sub_key=None, interval=10, debug=False):
        threading.Thread.__init__(self)
        self.daemon = True

        self.interval = interval
        self.tz = datetime.timezone(datetime.timedelta(0))

        self.debug = debug
        # Set up logging to file if debug is False
        if not debug:
            logging.basicConfig(filename='node.log', level=logging.INFO)
        else:
            logging.basicConfig(level=logging.DEBUG)

        self.switch = True

        # This is the alternative to keeping secrets on the Pi
        while pub_key is None or sub_key is None:
            if pub_key is None:
                while True:
                    p1 = input("Enter your publishing key: ")
                    if len(p1) != 42:
                        print("Your publishing key is too short!")
                    else:
                        pub_key = p1
                        break
            if sub_key is None:
                while True:
                    s1 = input("Enter your subscription key: ")
                    if len(s1) != 42:
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
        self.pubnub = PubNub(pnconfig)
        logging.info("Connected with SSL set to {}".format(pnconfig.ssl))

        logging.info("Setting up GPS service")
        self.gps_svc = gps.CoordinateService(gps_device)
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
        # # Do math to find distance from a known anchor point
        pass

        logging.info("Setting up BLE scanning service")
        self.scan_svc = scan.ScanService(pub_key, sub_key, not debug, NODE, NODE_COORDS)
        logging.info("Starting BLE scanner")
        self.scan_svc.scan()

        logging.info("Node initialized")
        time.sleep(0.1)

    def _publish_callback(self, result, status):
        # TODO
        pass
        # Check whether request successfully completed or not
        # s = None
        # if not status.is_error():
            # s = "No error"
            # del self.msg_queue[0]  # Message successfully published to specified channel.
        # elif status.category == PNStatusCategory.PNAccessDeniedCategory:
            # RESTART BOTTLE FOR CONFIG
            # s = "Access Denied"
            # del self.msg_queue[0]
        # elif status.category == PNStatusCategory.PNBadRequestCategory:
            # s = "Bad Request"
            # # Maybe bad keys, or an SDK error
            # del self.msg_queue[0]
        # elif status.category == PNStatusCategory.PNTimeoutCategory:
            # s = "Timeout"
            # # Republish with exponential backoff
            # msg_tuple = self.msg_queue[0]
            # message = msg_tuple[0]
            # timestamp = msg_tuple[1]
            # retry_time = msg_tuple[2]

            # while datetime.now() > retry_time:
            #     sleep(0.5)
            #
            # del self.msg_queue[0]
            #
            # now = datetime.now()
            # retry_time = now + timedelta(seconds=(now - timestamp).total_seconds())
            # self.msg_queue.append((message, timestamp, retry_time))
            #
            # self.pubnub.publish() \
            #     .channel('raw_channel') \
            #     .message(message) \
            #     .async(self._publish_callback)

    def _publish(self):
        if not self.debug:
            msgs = self.scan_svc.retrieve_in_view(reset=True)

            main_msg = {
                "device_uid": NODE,
                "message_uid": str(uuid.uuid1()),
                "timestamp": datetime.datetime.now(tz=self.tz).isoformat(),
                "location": self.gps_svc.get_latest_fix(),
                "in_view": {"msg_count": sum([len(v) for k, v in msgs.items()]),
                            "devices": list(msgs.keys()),
                            "raw": msgs},
                "tlm": {},
            }
            self.pubnub.publish() \
                .channel('node_raw') \
                .message(main_msg) \
                .should_store(True) \
                .async(self._publish_callback)
        else:
            msgs = self.scan_svc.retrieve_in_view(reset=True)

            print({
                "gps": self.gps_svc.get_latest_fix(),
                "in_view": {"msg_count": sum([len(v) for k, v in msgs.items()]),
                            "device_count": len(msgs.keys())},
            })

    def run(self):
        clock = timer()  # Start a clock and publish a message on a timer
        msg_alarm = 1  # Set to 1 to start with a message immediately

        # old_mod and new_mod get compared. Every X seconds (where X is
        #   the interval) we will notice the new_mod fall below the
        #   old_mod (ie: we passed another factor of interval). That's
        #   when we should fire the message off! This method is nice
        #   because it doesn't wander over time like threading.Timer or
        #   a simple implementation of time.sleep.
        old_mod = 0.0
        while self.switch:
            if msg_alarm:  # We only send a message when the message alarm goes off
                self._publish()
                msg_alarm = 0

            elapsed = timer() - clock
            new_mod = elapsed % self.interval

            if new_mod < old_mod and not msg_alarm:
                msg_alarm = 1
                # if self.debug:
                #     # Verify the thing isn't slowing down - it works!
                #     print("{:5f}".format(new_mod))
                if clock > 600:
                    clock = timer()
            old_mod = new_mod
            time.sleep(0.1)

    def terminate(self):
        logging.info("Shutting down GPS service")
        self.gps_svc.shutdown()
        logging.info("Shutting down BLE scanner")
        self.scan_svc.stop()
        logging.info("Shutting down node")
        self.switch = False
        self.join(3.0)
        logging.info("done")
