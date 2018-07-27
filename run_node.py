#!

import argparse
import os
from pathlib import Path

import dotenv

from node import Node

"""
The node needs publish and subscribe keys.

To get them, it will look in order of:
  1. Command-line arguments --pub and --sub
  2. The pubnub.env file
  3. Existing environment variables
  4. Command-line input
  5. Command-line input from the Node class

The pubnub.env file is automatically created on registration
  with the app.src.node_register.py app (Bottle page).
  
NOTE: If you have a pubnub.env file with bad keys it will 
  overwrite your existing keys!
"""
env = Path('./pubnub.env')
if env.exists():
    dotenv.load_dotenv(str(env.absolute()))
pub = os.environ.get("PUB_KEY", None)
sub = os.environ.get("SUB_KEY", None)

parser = argparse.ArgumentParser(
    description='Start a BLE scanning node.'
)

parser.add_argument(
    '--port', default='/dev/ttyACM0',
    help='Specify your device location (/dev/ttyXXX0)'
)
parser.add_argument(
    '--pub', help='Your publish key'
)
parser.add_argument(
    '--sub', help='Your subscribe key'
)
parser.add_argument(
    '--interval', type=int, default=300000,
    help='Interval between messages from node in milliseconds'
)
parser.add_argument(
    '--debug', action='store_true',
    help='Set debug mode; print messages (not published)',
    default=False
)
args = parser.parse_args()

# Choose or ask for publish key
if args.pub:
    if args.pub != '':
        pub = args.pub

# Choose or ask for subscribe key
if args.sub:
    if args.sub != '':
        sub = args.sub

if not pub:
    pub = input("What is your publish key?")
if not sub:
    sub = input("What is your subscribe key?")

args.interval = args.interval / 1000.0

node = Node(args.port, pub_key=pub, sub_key=sub,
            interval=args.interval, debug=args.debug)
node.start()
