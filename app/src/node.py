import argparse
import datetime
import json
import logging
import os
import sys
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
except ImportError as e:
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

MSG_LOG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'msg_log_{}'.format(datetime.datetime.now().strftime("%Y%m%d_%H%M"))
)


class Node(threading.Thread):
    def __init__(self, gps_device, pub_key=None, sub_key=None, interval=30, debug=False):
        threading.Thread.__init__(self)
        self.daemon = False

        self.interval = interval
        self.tz = datetime.timezone(datetime.timedelta(0))

        self.debug = debug
        if self.debug:
            print("Writing to {}".format(MSG_LOG))
            print("*** Debug messages are not complete messages.")

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

        logging.info("Setting up BLE scanning service")
        # TODO: This is blocking when run in terminal (aka how we do on Raspberry Pi)
        self.scan_svc = scan.BleMonitor()
        self.scan_svc.daemon = True

        logging.info("Node initialized - ready for start")

    def _publish_callback(self, result, status):
        # TODO: All of this

        # Check whether request successfully completed or not
        if not status.is_error():
            self.scan_svc.reset_in_view(status_to_remove=status.uuid)
        # s = "No error"  # remove post-debug
        # del self.msg_queue[0]  # Message successfully published to specified channel.
        # elif status.category == PNStatusCategory.PNAccessDeniedCategory:
        # RESTART BOTTLE FOR CONFIG IF STOPPED
        # s = "Access Denied"  # remove post-debug
        # del self.msg_queue[0]
        # elif status.category == PNStatusCategory.PNBadRequestCategory:
        # s = "Bad Request"  # remove post-debug
        # # Maybe bad keys, or an SDK error
        # del self.msg_queue[0]
        # elif status.category == PNStatusCategory.PNTimeoutCategory:
        # s = "Timeout"  # remove post-debug
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

    def _log_and_publish(self, log=True):

        now = datetime.datetime.now()
        previous = now - datetime.timedelta(seconds=self.interval)

        msg_id = str(uuid.uuid1())
        msgs = self.scan_svc.retrieve_in_view(reset=True, set_status=msg_id)

        location = self.gps_svc.get_latest_fix()
        if location:
            is_old_location = int(location[3] >= previous)
            location[3] = location[3].isoformat()
        else:
            is_old_location = 0

        main_msg = {
            "device_uid": NODE,
            "message_uid": msg_id,
            "timestamp": datetime.datetime.now(tz=self.tz).isoformat(),
            "location": self.gps_svc.get_latest_fix(),
            "is_old_location": is_old_location,
            "in_view": {"msg_count": sum([len(v) for k, v in msgs.items()]),
                        "devices": list(msgs.keys()),
                        "raw": msgs},
            "tlm": {},
        }

        if log:
            with open(MSG_LOG, 'a') as msg_log:
                msg_log.writelines([json.dumps(main_msg), "\n"])

        if not self.debug and self.pubnub:
            result, status = self.pubnub.publish() \
                .channel('node_raw') \
                .message(main_msg) \
                .should_store(True) \
                .async(self._publish_callback)
            self.scan_svc.reset_in_view(status_to_remove=msg_id,
                                        new_status=status.uuid)
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
                self._log_and_publish()
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
        self.scan_svc.terminate()
        logging.info("Shutting down node")
        self.switch = False
        self.join(3.0)
        logging.info("done")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Start a BLE scanning node.'
    )
    parser.add_argument(
        'port', metavar='port',
        help='Specify your device location (/dev/ttyXXX0)'
    )
    parser.add_argument(
        '--pub', required=True, help='Your publishing key'
    )
    parser.add_argument(
        '--sub', required=True, help='Your subscription key'
    )
    parser.add_argument(
        '--interval', type=int, default=10000,
        help='Interval between messages from node in milliseconds'
    )
    parser.add_argument(
        '--debug', action='store_true',
        help='Set debug mode; print messages (not published)',
        default=False
    )
    args = parser.parse_args()

    args.interval = args.interval / 1000.0
    node = Node(args.port,
                pub_key=args.pub,
                sub_key=args.sub,
                interval=args.interval,
                debug=args.debug)
    node.daemon = False
    node.start()
    node.join()
