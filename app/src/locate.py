import dateutil.parser
import math

from collections import defaultdict, deque
from datetime import timedelta

# from pubnub.enums import PNStatusCategory
from pubnub.pnconfiguration import PNConfiguration
from pubnub.pubnub import PubNub

from app.src.trilateration import TrilaterationSolver

class MaxLenDeque(deque):
    def __init__(self):
        maxlen = 6
        super(MaxLenDeque, self).__init__(maxlen=maxlen)


class BeaconLocator(object):
    def __init__(self, pub_key, sub_key, ):
        pnconfig = PNConfiguration()
        pnconfig.subscribe_key = sub_key
        pnconfig.publish_key = pub_key
        pnconfig.ssl = False

        self.pubnub = PubNub(pnconfig)

        # Holds messages from the 'ranged' topic
        self.message_log = defaultdict(MaxLenDeque)
        self.max_time_diff = timedelta(seconds=3)

        self.n = 1.8  # Path loss exponent = 1.6-1.8 w/LOS to beacon indoors
        self.c = 10  # Env constant (c) = error reduction const by env testing
        self.A0 = 23  # Average RSSI value at d0 (1 meter)
        self.tx_power = 23  # Transmit power in dBm

        self.solver = TrilaterationSolver()

    def _publish_range(self, bt_addr, rssi, timestamp, distance, node):
        message = [bt_addr, rssi, timestamp, distance, node]
        self.pubnub.publish() \
            .channel('ranged') \
            .message(message) \
            .should_store(True) \
            .async(self._publish_callback)

    def _publish_coords(self, bt_addr, timestamp, coords, meta=None):
        if meta is None:
            meta = {}
        message = [bt_addr, timestamp, coords, meta]
        self.pubnub.publish() \
            .channel('located') \
            .message(message) \
            .should_store(True) \
            .async(self._publish_callback)

    def _publish_callback(self, result, status):
        # Check whether request successfully completed or not
        # Try to handle errors intelligently...
        pass

    def _range(self, message, channel):
        bt_addr = message[0]
        bt_rssi = message[1]
        log_slot = self.message_log[bt_addr]

        # Based on the LSM from Ewen Chou's bluetooth-proximity project
        # https://github.com/ewenchou/bluetooth-proximity
        # Very naive, no Kalman filters, no measurement/calibration
        x = float((bt_rssi - self.A0) / (-10 * self.n))
        distance = (math.pow(10, x) * 100) + self.c

        # Alternative
        # distance = 10 ^ ((self.tx_power - bt_rssi) / (10 * self.n))

        self._publish_range(bt_addr, bt_rssi, message[4], distance, message[5])
        log_slot.appendleft(message)

        # Find earliest acceptable time to consider in location
        msg_dt = dateutil.parser.parse(message[4])
        min_time = msg_dt - self.max_time_diff

        # Do location and publish if appropriate
        self._locate(log_slot, bt_addr, message[4], min_time)

    def _locate(self, log_slot, bt_addr, msg_timestamp, min_time):
        # check stack of messages time constraints
        applicable_msgs = [msg for msg in log_slot
                           if dateutil.parser.parse(msg[4]) >= min_time]

        # do best location possible w/ available nodes/raw messages
        location = (0, 0)
        meta = {"error": 0,
                "nodes": 0}

        # publish location (with error and/or other metadata if possible)
        self._publish_coords(bt_addr, msg_timestamp, location, meta)

    def start(self):
        self.pubnub.subscribe().channels('raw_channel') \
            .execute().async(self._range)

    def stop(self):
        self.pubnub.unsubscribe_all()
