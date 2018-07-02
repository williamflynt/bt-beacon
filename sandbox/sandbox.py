import math
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


def raw_iq(filename="FMcapture1.dat"):
    from mpl_toolkits.mplot3d import Axes3D
    from matplotlib import cm
    import matplotlib.pyplot as plt
    import numpy

    def coords3d(i, q):
        a = (i ** 2 + q ** 2) ** 0.5
        return (i,
                q,
                math.degrees(math.acos(i / a)))

    script_dir = os.path.abspath(__file__)
    base_dir = os.path.dirname(script_dir)
    i_list = []
    q_list = []
    with open(os.path.join(base_dir, filename), "rb") as f:
        content = [x - 127.5 for x in f.read()]
        i_list = content[::2]
        q_list = content[1::2]
    pairs = zip(i_list, q_list)
    coords = []
    for i in range(2000):
        pair = pairs.__next__()
        coords.append(coords3d(*pair))

    # for pair in pairs:
    #     i = pair[0]
    #     q = pair[1]
    #     a = (i ** 2 + q ** 2) ** 0.5
    #     deg = math.degrees(math.acos(i / a))
    #     print("I = {:.2f}\nQ = {:.2f}\nA = {:.2f}".format(i, q, a))
    #     print("{:.2f} = {:.2f} * cos({:.2f}\xb0)".format(
    #         i, a, deg
    #     ))
    #     x = input("Any key or Ctrl-C")
    #     if x == 'quit':
    #         break

    # # Simple 3D Scatter
    # fig = plt.figure()
    # ax = fig.add_subplot(111, projection='3d')
    #
    # for coord in coords:
    #     i = coord[0]
    #     q = coord[1]
    #     deg = coord[2]
    #     color = (
    #         abs(i/127.5),
    #         abs(q/127.5),
    #         deg/360.0
    #     )
    #     ax.scatter(i, q, deg, c=color, marker="o")
    #
    # ax.set_xlabel('I')
    # ax.set_ylabel('Q')
    # ax.set_zlabel('Theta')
    #
    # plt.show()

    import numpy as np

    X = numpy.asarray([coord[0] for coord in coords])
    Y = numpy.asarray([coord[1] for coord in coords])
    X, Y = np.meshgrid(X, Y)
    A = np.sqrt(X ** 2 + Y ** 2)
    Z = np.rad2deg(np.arccos(X / A))

    fig = plt.figure()
    ax = Axes3D(fig)
    ax.plot_surface(X, Y, Z, rstride=1, cstride=1, cmap=cm.viridis)

    plt.show()


def test_plot():
    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib import cm
    from mpl_toolkits.mplot3d import Axes3D

    X = np.arange(-127.5, 127.5, 1)
    Y = np.arange(-127.5, 127.5, 1)
    X, Y = np.meshgrid(X, Y)
    A = np.sqrt(X ** 2 + Y ** 2)
    Z = np.rad2deg(np.arccos(X / A))

    fig = plt.figure()
    ax = Axes3D(fig)
    ax.plot_surface(X, Y, Z, rstride=1, cstride=1, cmap=cm.viridis)

    plt.show()
