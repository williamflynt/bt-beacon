import dateutil.parser

from collections import defaultdict, deque
from datetime import timedelta
from statistics import mean, harmonic_mean as hmean

from pubnub.callbacks import SubscribeCallback
# from pubnub.enums import PNStatusCategory
from pubnub.pnconfiguration import PNConfiguration
from pubnub.pubnub import PubNub

try:
    from app.src.trilateration import TrilaterationSolver
except ModuleNotFoundError as e:
    from trilateration import TrilaterationSolver


class MaxLenDeque(deque):
    def __init__(self, maxlen=30):
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
        self.raw_log = defaultdict(MaxLenDeque)
        self.ranged_log = defaultdict(MaxLenDeque)
        self.max_time_diff = timedelta(seconds=5)

        # n_matrix = {
        #     "indoors": 3.7,
        #     "free_air": 2,
        # }
        # beacon_matrix = {
        #     "bluecharm": -59.8,
        # }
        self.n = 3.7  # Path loss exponent = 1.6-1.8 w/LOS to beacon indoors
        self.measured_rssi = -59.8  # Beacon-specific measured RSSI @ 1m

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

    def _publish_location(self, bt_addr, timestamp, coords, meta=None):
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
        pass  # Pretty intelligent, huh?

    def _range(self, message, channel):
        bt_addr = message[0]
        node_name = message[5]
        raw_log_slot = self.raw_log[bt_addr]
        ranged_log_slot = self.ranged_log[bt_addr]

        raw_log_slot.appendleft(message)
        # Find earliest acceptable time to consider in location
        msg_dt = dateutil.parser.parse(message[4])
        min_time = msg_dt - self.max_time_diff
        # Find average RSSI for the node over the allowable time period and
        #  use this average value for range calculations for dampening
        # applicable_rssi = [
        #     msg[1] for msg in raw_log_slot
        #     if dateutil.parser.parse(msg[4]) >= min_time
        #     and msg[5] == node_name  # matching node_name
        # ]
        # avg_rssi = mean(applicable_rssi)

        applicable_rssi = [
            -msg[1] for msg in raw_log_slot
            if dateutil.parser.parse(msg[4]) >= min_time
               and msg[5] == node_name  # matching node_name
        ]
        # harmonic mean (vs arithmatic mean) dampens the wild swings
        avg_rssi = -hmean(applicable_rssi)

        # print(applicable_rssi)
        # print("{}: {}".format(node_name, avg_rssi))

        # Calculate distance from bt_rssi, assuming tx_power and n
        distance = 10 ** ((self.measured_rssi - avg_rssi) / (10 * self.n))

        # message[4] is timestamp in messages from 'raw_channel'
        # message[5] is node name in messages from 'raw_channel'
        ranged_message = [bt_addr, avg_rssi, message[4], distance, message[5]]
        self._publish_range(*ranged_message)
        ranged_log_slot.appendleft(ranged_message)

        # Do location and publish if appropriate
        self._locate(ranged_log_slot, bt_addr, message[4], min_time)

    def _locate(self, ranged_log_slot, bt_addr, msg_timestamp, min_time):
        # log_slot is a list of 'ranged' messages like:
        # # [bt_addr, bt_rssi, timestamp, distance, nodename]
        # check stack of messages for those within time constraints
        applicable_msgs = [msg for msg in ranged_log_slot
                           if dateutil.parser.parse(msg[2]) >= min_time]

        nodes = list(set([msg[4] for msg in applicable_msgs]))
        node_count = len(nodes)
        for node in nodes:
            if node not in self.known_nodes:
                self.get_nodes()

        if node_count > 1:
            # Get the average range for each node
            averaged = defaultdict(list)
            for msg in applicable_msgs:
                averaged[msg[4]].append(msg)
            use_these = []
            # Apply the average to all messages from the node
            for nodename, msg_list in averaged.items():
                observed = [msg[3] for msg in msg_list]
                for msg in msg_list:
                    msg[3] = mean(observed)
                use_these.extend(msg_list)
            locations, distances = zip(*[
                (self.node_map[msg[4]], msg[3])
                for msg in use_these
                if msg[4] in self.known_nodes
            ])

            # # Doesn't use any average range calculation,
            # #  just the most recent one reported for node.
            # latest = defaultdict(bool)
            # for msg in applicable_msgs:
            #     bt_addr = msg[4]
            #     msg_dt = dateutil.parser.parse(msg[2])
            #     if not latest[bt_addr] or dateutil.parser.parse(latest[bt_addr][2]) < msg_dt:
            #         latest[bt_addr] = msg
            # use_these = [v for k, v in latest.items() if v]
            # locations, distances = zip(*[
            #     (self.node_map[msg[4]], msg[3])
            #     for msg in use_these
            #     if msg[4] in self.known_nodes
            # ])

            # print("***")
            # print(use_these)
            # print(locations)
            # print(distances)

            # do best location possible w/ available nodes/messages
            result = self.solver.best_point(locations, distances)
            coords = result['coords']
            meta = {"avg_err": result['avg_err'],
                    "message_count": len(applicable_msgs),
                    "node_count": node_count,
                    "nodes": str(nodes)}

            # publish location (with error and/or other metadata if possible)
            self._publish_location(bt_addr, msg_timestamp, coords, meta)

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
