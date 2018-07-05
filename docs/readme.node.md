# Node

This is a location-aware, BLE-scanner node that reports back to PubNub.
It's designed on Python 3.6 for a Raspberry Pi 3 running Raspbian.
Although untested, it will likely work on most flavors of Linux.

### Hardware

In addition to the Raspberry Pi, this package uses a GPS dongle from Amazon ($15). 
It's a USB device sold by DIYMall, and it's based on the U-blox 7 chipset.
For mobility of the node (required for functionality) I also used a battery pack for the Pi, also available on Amazon.

### Installation

It's important to install this package outside your home directory, due to mount options at boot
and incompatibility with permissions requirements (capabilities and Bluetooth devices).

~~~
cd /opt
export DIRNAME=bluedev
sudo mkdir $DIRNAME && sudo chown $USER:$USER $DIRNAME
cd $DIRNAME
~~~

For now, clone the repo. Then:

1. Make a virtual environment and use it like: `venv . && source ./bin/activate`
2. Follow the setup in `readme.scan.md` under the **Installing** heading to make sure your BLE scanner works.
3. Install the requirements like: `pip install -r app/requirements.txt` if you haven't yet.
4. Make sure your GPS device is plugged into the USB.
5. Set up GPS device permissions for the user that will be running the node. `sudo chmod 666 /dev/ttyACM0`
6. Run the node.

### Usage

You can test your GPS and BLE scanner by using a basic testing node. It doesn't publish anything to PubNub.
In your Python terminal:

~~~pythonstub
# Where /dev/ttyACM0 is your GPS device
from time import sleep
from app.src.node import *
node = Node('/dev/ttyACM0', 'demo', "demo", 3, True)
node.start()
sleep(5)
node.terminate()
~~~

If that doesn't work, common errors are not setting GPS permissions, Bluetooth is off,
or Bluetooth `setcap` didn't work/not accomplished.


For an actual node:

~~~python
# Optionally pass interval (integer - time between messages to PubNub)
# You'll want to use your actual publish/subscribe keys here
from app.src.node import Node
node = Node('/dev/ttyACM0', 'demo', "demo")
node.start()
~~~