#!/usr/bin/env python

import os
import pytz

from pubnub.enums import PNStatusCategory
from pubnub.pnconfiguration import PNConfiguration
from pubnub.pubnub import PubNub
from time import sleep

from datetime import datetime, timedelta

from beacontools import BeaconScanner

UTC = pytz.timezone('UTC')


# try:
#     NODE = os.environ['NODE_NAME']
#     NODE_COORDS = (
#         os.environ['NODE_X'], os.environ['NODE_Y']
#     )
# except KeyError as e:
#     print('You must define three environment variables:')
#     print('NODE   = The name of the node.')
#     print('NODE_X = The x-coordinate of the node in meters.')
#     print('NODE_Y = The x-coordinate of the node in meters.')
#     quit()


class ScanService(object):
    def __init__(self, pub_key, sub_key, publish=True):
        self.publish = publish
        self.msg_queue = []
        self.scanner = None

        pnconfig = PNConfiguration()
        pnconfig.subscribe_key = sub_key
        pnconfig.publish_key = pub_key
        pnconfig.ssl = False

        self.pubnub = PubNub(pnconfig)

    def _publish_callback(self, result, status):
        # Check whether request successfully completed or not
        if not status.is_error():
            del self.msg_queue[0]  # Message successfully published to specified channel.
        elif status.category == PNStatusCategory.PNAccessDeniedCategory:
            del self.msg_queue[0]
        elif status.category == PNStatusCategory.PNBadRequestCategory:
            # Maybe bad keys, or an SDK error
            del self.msg_queue[0]
        elif status.category == PNStatusCategory.PNTimeoutCategory:
            # Republish with exponential backoff
            msg_tuple = self.msg_queue[0]
            message = msg_tuple[0]
            timestamp = msg_tuple[1]
            retry_time = msg_tuple[2]

            while datetime.now() > retry_time:
                sleep(0.5)

            del self.msg_queue[0]

            now = datetime.now()
            retry_time = now + timedelta(seconds=(now - timestamp).total_seconds())
            self.msg_queue.append((message, timestamp, retry_time))

            self.pubnub.publish() \
                .channel('raw_channel') \
                .message(message) \
                .async(self._publish_callback)

    def _publish(self, bt_addr, rssi, packet, additional_info):
        if not self.publish:
            pass
        else:
            now = datetime.now(UTC)
            # The actual message body
            message = [bt_addr,
                       rssi,
                       "{}".format(packet),
                       "{}".format(additional_info),
                       now.isoformat(),
                       NODE]
            retry_time = now + timedelta(seconds=5)
            self.msg_queue.append((message, now, retry_time))

            self.pubnub.publish() \
                .channel('raw_channel') \
                .message(message) \
                .should_store(True) \
                .async(self._publish_callback)

    def scan(self):
        init_message = {"name": NODE,
                        "coords": {
                            "x": NODE_COORDS[0],
                            "y": NODE_COORDS[1]
                        }}
        self.pubnub.publish() \
            .channel('nodes') \
            .message(init_message) \
            .should_store(True) \
            .sync()
        print("{} at coords {}".format(NODE, NODE_COORDS))
        self.scanner = BeaconScanner(self._publish)
        self.scanner.start()

    def stop(self):
        self.scanner.stop()


if __name__ == "__main__":
    """
    Call scan.py like:
      python scan.py pub_key sub_key
    or
      python scan.py pub_key sub_key publish
    or
      python scan.py pub_key sub_key NODE_NAME NODE_X NODE_Y [publish]
    """
    import sys

    publish = True

    if len(sys.argv) < 3:
        print("Call scan.py like:")
        print("  python scan.py pub_key sub_key [publish]")
        print("or")
        print("  python scan.py pub_key sub_key NODE_NAME NODE_X NODE_Y [publish]")
        quit()
    elif len(sys.argv) < 6:
        try:
            NODE = os.environ['NODE_NAME']
            NODE_COORDS = (
                os.environ['NODE_X'], os.environ['NODE_Y']
            )
        except KeyError as e:
            print('Error: Missing NODE_NAME NODE_X NODE_Y from command.')
            print('You can also define three environment variables:')
            print('NODE   = The name of the node.')
            print('NODE_X = The x-coordinate of the node in meters.')
            print('NODE_Y = The x-coordinate of the node in meters.')
            quit()
    elif len(sys.argv) == 6:
        NODE = sys.argv[3]
        NODE_COORDS = (
            float(sys.argv[4]), float(sys.argv[5])
        )
    elif len(sys.argv) > 6:
        NODE = sys.argv[3]
        NODE_COORDS = (
            float(sys.argv[4]), float(sys.argv[5])
        )
        publish = sys.argv[6]

    scanner = ScanService(sys.argv[1], sys.argv[2], publish)
    scanner.scan()
