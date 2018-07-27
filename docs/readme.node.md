# Node

This is a location-aware BLE-scanner node that reports back to PubNub.
It's designed on Python 3.5+ for a Raspberry Pi 3 running Raspbian Stretch.
Although untested, it will likely work on most flavors of Debian.

### Hardware

In addition to the Raspberry Pi, this package uses a GPS dongle from Amazon ($15). 
It's a USB device sold by DIYMall, and it's based on the U-blox 7 chipset.
For mobility of the node I used a battery pack for the Pi, also available on Amazon.

### Installation

It's important to install this package outside your home directory, due to mount options at boot
and incompatibility with permissions requirements (capabilities and Bluetooth devices).

1. Plug your GPS dongle in, and verify the path to it (ex: `/dev/ttyACM0`)
2. Clone the repo and run the setup script, like:
 
~~~bash
cd /opt
sudo git clone https://github.com/williamflynt/bt-beacon.git
chown -R ${USER}:${USER} ./bt-beacon
cd ./bt-beacon
chmod +x ./node_setup.sh
./node_setup.sh

~~~

### Usage

This assumes you have a credential server set up. If not, see Testing Usage below.

You've successfully set up your node, and now you have a node registration service.
The service uses a simple `bottle.py` app to communicate with the server.
When you provide a valid user/pass combo, the server returns PubNub keys.

1. Navigate to your Pi's IP at port 8765, like `http://192.168.0.109:8765`. 
2. Enter your registration credentials.
3. The Pi will set up your environment with PubNub keys from the credential server.
4. Your node service (actual GPS/BLE scanner) will also be enabled with `systemctl`.

Messages should start being published to your PubNub account immediately.
 
### Testing Usage

You may not have a credentials server set up. That's fine.

You can test your GPS and BLE scanner manually, with or without publishing messages.
In your Python terminal:

~~~python
# Where /dev/ttyACM0 is your GPS device
from time import sleep
from app.src.node import *
node = Node('/dev/ttyACM0', pub_key='demo', sub_key="demo", interval=3, debug=True)
node.start()
sleep(15)
node.terminate()
~~~

For an actual node, we can enter the keys on the command line, or provide them in the initial command like before.

~~~python
from app.src.node import Node
node = Node('/dev/ttyACM0')
node.start()
~~~

You can also use `run_node.py` directly, like:

~~~bash
run_node.py /dev/ttyACM0 --pub demo --sub demo &
~~~
~~~bash
run_node.py --interval 30000
~~~
~~~bash
run_node.py --help
~~~


### PubNub Keys

The node needs publish and subscribe keys for PubNub to operate with `publish=True`.

To get them, `run_node.py` will look in order of:
  1. Command-line arguments `--pub` and `--sub`
  2. The `pubnub.env` file
  3. Environment variables `PUB_KEY` and `SUB_KEY`
  4. Command-line input from `run_node.py`
  5. Command-line input from the `Node` class `__init__`
  
So you have lots of chances.

The `pubnub.env` file is automatically created on registration with the `app.src.node_register.py` app.
  
**Note:** If you have a pubnub.env file with bad keys it will take priority over environment keys!

### Common Setup Problems

If setup doesn't work, common errors are:
1. Not setting GPS permissions to `666`
2. Not setting directory permissions on the repo for the current user
3. Bluetooth is off
4. `node_setup.sh` commands for `setcap` didn't work/not accomplished
5. Repo cloned in a directory with improper mount options at boot (ie: `/home/yourfolder`)