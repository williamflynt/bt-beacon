import os
import time
from beacontools import BeaconScanner, EddystoneTLMFrame, EddystoneFilter


def callback(bt_addr, rssi, packet, additional_info):
    print("<%s, %d> %s %s" % (bt_addr, rssi, packet, additional_info))


def test_scan(timesleep=10):
    # scan for all TLM frames of beacons in the namespace "12345678901234678901"
    scanner = BeaconScanner(callback,
                            # device_filter=EddystoneFilter(namespace="12345678901234678901"),
                            # packet_filter=EddystoneTLMFrame
                            )
    i = 0
    if timesleep:
        print("Scanning for {} seconds...".format(timesleep))
        scanner.start()
        time.sleep(timesleep)
        scanner.stop()
    else:
        scanner.start()
        while True:
            print("Scanning: {} seconds...".format(i * 5))
            time.sleep(5)
            i += 1
