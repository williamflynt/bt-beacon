#!/usr/bin/env python

import os
import pytz

from pubnub.enums import PNStatusCategory
from pubnub.pnconfiguration import PNConfiguration
from pubnub.pubnub import PubNub
from collections import defaultdict
from datetime import datetime, timedelta
from time import sleep

# from beacontools import BeaconScanner
from beacontools.scanner import Monitor

UTC = pytz.timezone('UTC')


class BleMonitor(Monitor):
    def __init__(self, pub_key=None, sub_key=None, publish=False, node_name=None, node_coords=(0, 0)):
        Monitor.__init__(self, self._on_receive, 0, None, None)
        self.publish = publish
        self.node_name = node_name
        self.node_coords = node_coords
        self.msg_queue = []

        # For tracking beacons in view of scanner over time
        self.in_view = []

        if self.publish:
            if not pub_key or not sub_key or not node_name:
                print("This BLE Scanner is set up for demo only.")
                pub_key = "demo"
                sub_key = "demo"
                self.node_name = "demo"
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

    def _on_receive(self, bt_addr, rssi, packet, properties):
        now = datetime.now(UTC)

        # Running log of the last message from each beacon seen since start
        # of this service.
        self.in_view.append(
            {
                "device_id": bt_addr,
                "rssi": rssi,
                "message": "{}".format(packet),
                "time": now.isoformat(),
                "status": "unpublished"
            }
        )

        if self.publish:
            # The actual message body
            message = [bt_addr,
                       rssi,
                       "{}".format(packet),
                       "{}".format(properties),
                       now.isoformat(),
                       self.node_name]
            retry_time = now + timedelta(seconds=5)
            self.msg_queue.append((message, now, retry_time))

            self.pubnub.publish() \
                .channel('raw_channel') \
                .message(message) \
                .should_store(True) \
                .async(self._publish_callback)

    def retrieve_in_view(self, fetch_status='unpublished',
                         set_status='retrieved',
                         reset=False):
        temp_msgs = defaultdict(list)
        for msg in self.in_view:
            if msg['status'] == fetch_status:
                device_id = msg['device_id']
                temp_msgs[device_id].append(msg)
                msg['status'] = set_status
        if reset:
            self.reset_in_view()
        return temp_msgs

    def reset_in_view(self, hard=False, status_to_remove='published'):
        if hard:
            self.in_view = []
        else:
            self.in_view = [msg for msg in self.in_view
                            if msg['status'] != status_to_remove]


class ScanService(object):
    def __init__(self, pub_key, sub_key, publish=True, node_name=None, node_coords=(0, 0)):
        self.publish = publish
        self.node_name = node_name
        self.node_coords = node_coords
        self.msg_queue = []
        self.scanner = None

        # For tracking beacons in view of scanner over time
        self.in_view = []

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

    def _on_receive(self, bt_addr, rssi, packet, additional_info):
        now = datetime.now(UTC)

        # Running log of the last message from each beacon seen since start
        # of this service.
        self.in_view.append(
            {
                "device_id": bt_addr,
                "rssi": rssi,
                "message": "{}".format(packet),
                "time": now.isoformat(),
                "status": "unpublished"
            }
        )

        if not self.publish:
            pass
        else:
            # The actual message body
            message = [bt_addr,
                       rssi,
                       "{}".format(packet),
                       "{}".format(additional_info),
                       now.isoformat(),
                       self.node_name]
            retry_time = now + timedelta(seconds=5)
            self.msg_queue.append((message, now, retry_time))

            self.pubnub.publish() \
                .channel('raw_channel') \
                .message(message) \
                .should_store(True) \
                .async(self._publish_callback)

    def retrieve_in_view(self, reset=False):
        temp_msgs = defaultdict(list)
        for msg in self.in_view:
            device_id = msg['device_id']
            temp_msgs[device_id].append(msg)
            msg['status'] = "published"
        if reset:
            self.reset_in_view()
        return temp_msgs

    def reset_in_view(self, hard=False):
        if hard:
            self.in_view = []
        else:
            self.in_view = [msg for msg in self.in_view if msg['status'] == 'unpublished']

    def scan(self):
        init_message = {"name": self.node_name,
                        "coords": {
                            "x": self.node_coords[0],
                            "y": self.node_coords[1]
                        }}
        self.pubnub.publish() \
            .channel('nodes') \
            .message(init_message) \
            .should_store(True) \
            .sync()
        # print("{} at coords {}".format(self.node_name, self.node_coords))
        self.scanner = Monitor(self._on_receive, 0, None, None)
        # self.scanner = BeaconScanner(self._on_receive)
        self.scanner.start()

    def stop(self):
        self.scanner.terminate()


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

    scanner = ScanService(sys.argv[1], sys.argv[2], publish, NODE, NODE_COORDS)
    scanner.scan()
