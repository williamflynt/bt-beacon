import dateutil.parser

from collections import defaultdict, deque
from datetime import timedelta

from pubnub.callbacks import SubscribeCallback
# from pubnub.enums import PNStatusCategory
from pubnub.pnconfiguration import PNConfiguration
from pubnub.pubnub import PubNub

try:
    from app.src.trilateration import TrilaterationSolver
except ModuleNotFoundError as e:
    from trilateration import TrilaterationSolver


class MaxLenDeque(deque):
    def __init__(self):
        maxlen = 6
        super(MaxLenDeque, self).__init__(maxlen=maxlen)


class BeaconLocator(SubscribeCallback):
    def __init__(self, pub_key, sub_key):
        pnconfig = PNConfiguration()
        pnconfig.subscribe_key = sub_key
        pnconfig.publish_key = pub_key
        pnconfig.ssl = False

        self.pubnub = PubNub(pnconfig)
        self.node_map = defaultdict(tuple)
        self.known_nodes = []
        self.get_nodes()

        # Holds messages from the 'ranged' topic
        self.message_log = defaultdict(MaxLenDeque)
        self.max_time_diff = timedelta(seconds=5)

        self.n = 1.6  # Path loss exponent = 1.6-1.8 w/LOS to beacon indoors
        self.tx_power = -69.5  # Transmit power in dBm

        self.solver = TrilaterationSolver()

    def get_nodes(self):
        nodes_msgs = self.pubnub \
            .history() \
            .channel("nodes") \
            .count(100).sync()
        for m in nodes_msgs.result.messages:
            message = m.entry
            try:
                node = message['name']
                self.node_map[node] = (
                    message["coords"]["x"], message["coords"]["y"]
                )
                if node not in self.known_nodes:
                    self.known_nodes.append(node)
            except Exception as e:
                pass

    def _publish_range(self, bt_addr, rssi, timestamp, distance, node):
        message = [bt_addr, rssi, timestamp, distance, node]
        self.pubnub.publish() \
            .channel('ranged') \
            .message(message) \
            .should_store(True) \
            .async(self._publish_callback)

    def _publish_beacon_coords(self, bt_addr, timestamp, coords, meta=None):
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

        # Calculate distance from bt_rssi, assuming tx_power and n
        distance = 10 ** ((self.tx_power - bt_rssi) / (10 * self.n))

        # message[4] is timestamp in messages from 'raw_channel'
        ranged_message = [bt_addr, bt_rssi, message[4], distance, message[5]]
        self._publish_range(*ranged_message)
        log_slot.appendleft(ranged_message)

        # Find earliest acceptable time to consider in location
        msg_dt = dateutil.parser.parse(message[4])
        min_time = msg_dt - self.max_time_diff

        # Do location and publish if appropriate
        self._locate(log_slot, bt_addr, message[4], min_time)

    def _locate(self, log_slot, bt_addr, msg_timestamp, min_time):
        # log_slot is a list of 'ranged' messages like:
        # # [bt_addr, bt_rssi, timestamp, distance, nodename]
        # check stack of messages for those within time constraints
        applicable_msgs = [msg for msg in log_slot
                           if dateutil.parser.parse(msg[2]) >= min_time]

        nodes = list(set([msg[4] for msg in applicable_msgs]))
        node_count = len(nodes)
        if node_count > 1:
            for node in nodes:
                if node not in self.known_nodes:
                    self.get_nodes()
            locations, distances = zip(*[
                (self.node_map[msg[4]], msg[3])
                for msg in applicable_msgs
                if msg[4] in self.known_nodes
            ])

            # do best location possible w/ available nodes/raw messages
            result = self.solver.best_point(locations, distances)
            coords = result['coords']
            meta = {"avg_err": result['avg_err'],
                    "message_count": len(applicable_msgs),
                    "node_count": node_count,
                    "nodes": str(nodes)}

            # publish location (with error and/or other metadata if possible)
            self._publish_beacon_coords(bt_addr, msg_timestamp, coords, meta)

    def status(self, pubnub, status):
        pass

    def presence(self, pubnub, presence):
        pass

    def message(self, pubnub, msg):
        message = msg.message
        channel = msg.channel
        if channel == 'raw_channel':
            self._range(message, channel)
        elif channel == 'nodes':
            self.get_nodes()
        else:
            pass

    def start(self):
        self.pubnub.add_listener(self)
        self.pubnub.subscribe() \
            .channels(['raw_channel', 'nodes']) \
            .execute()

    def stop(self):
        self.pubnub.unsubscribe_all()


if __name__ == '__main__':
    import os
    import sys

    if len(sys.argv) == 1:
        try:
            sys.argv.append(os.environ['PUB_KEY'])
            sys.argv.append(os.environ['SUB_KEY'])
        except KeyError:
            print("Set the PUB_KEY and SUB_KEY arguments!")
            print('-  export PUB_KEY="<pub_key_here>"')
            print("Alternatively, run locate.py with those args, like:")
            print("-  python locate.py <pub_key> <sub_key>")
            quit()
    elif len(sys.argv) != 3:
        print("Run locate.py with two arguments: ")
        print("-  pub_key: a PubNub publishing key.")
        print("-  sub_key: a PubNub subscription key.")
        print("It looks like: ")
        print("-  python locate.py <pub_key> <sub_key>")
        quit()

    print(sys.argv)

    locator = BeaconLocator(sys.argv[1], sys.argv[2])
    locator.start()
