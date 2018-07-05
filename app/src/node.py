import datetime
import logging
import threading
import time
import uuid

from timeit import default_timer as timer

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
    def __init__(self, gps_device, pub_key, sub_key, interval=10, debug=False):
        threading.Thread.__init__(self)
        self.daemon = True

        self.interval = interval

        self.debug = debug
        # Set up logging to file if debug is False
        if not debug:
            logging.basicConfig(filename='node.log', level=logging.INFO)
        else:
            logging.basicConfig(level=logging.DEBUG)

        self.switch = True

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

    def run(self):
        # Start a clock and publish a message every X seconds
        tz = datetime.timezone(datetime.timedelta(0))
        while self.switch:
            if self.debug:
                msgs = self.scan_svc.retrieve_in_view(reset=True)
                print({
                    "gps": self.gps_svc.get_latest_fix(),
                    "in_view": {"msg_count": sum([len(v) for k, v in msgs.items()]),
                                "device_count": len(msgs.keys())},
                })
            else:
                msgs = self.scan_svc.retrieve_in_view(reset=True)
                print({
                    "device_uid": NODE,
                    "message_uid": uuid.uuid1(),
                    "timestamp": datetime.datetime.now(tz=tz),
                    "location": self.gps_svc.get_latest_fix(),
                    "in_view": {"msg_count": sum([len(v) for k, v in msgs.items()]),
                                "devices": msgs.keys(),
                                "raw": msgs},
                    "tlm": {}
                })
            time.sleep(self.interval)

    def terminate(self):
        logging.info("Shutting down GPS service")
        self.gps_svc.shutdown()
        logging.info("Shutting down BLE scanner")
        self.scan_svc.stop()
        logging.info("Shutting down node")
        self.switch = False
        self.join(0.5)
        logging.info("done")
