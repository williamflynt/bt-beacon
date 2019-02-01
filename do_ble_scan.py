#!

import argparse
import os
from pathlib import Path

import dotenv

try:
    from scan import ScanService
except ImportError:
    from app.src.scan import ScanService

"""
The node needs publish and subscribe keys.

To get them, it will look in order of:
  1. Command-line arguments --pub and --sub
  2. The pubnub.env file
  3. Existing environment variables
  4. Command-line input
"""
env = Path('./pubnub.env')
if env.exists():
    dotenv.load_dotenv(str(env.absolute()))
pub = os.environ.get("PUB_KEY", None)
sub = os.environ.get("SUB_KEY", None)
node = os.environ.get("HOSTNAME", None)
node_x = os.environ.get("NODE_X", 3)
node_y = os.environ.get("NODE_Y", 3)

parser = argparse.ArgumentParser(
    description='Start a BLE scanning node.'
)

parser.add_argument(
    '--pub', help='Your publish key'
)
parser.add_argument(
    '--sub', help='Your subscribe key'
)
parser.add_argument(
    '--node', help='Your hostname'
)
parser.add_argument(
    '--node_x', help='Your X position in meters'
)
parser.add_argument(
    '--node_y', help='Your Y position in meters'
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

if args.node:
    if args.node != '':
        node = args.node
if args.node_x:
    if args.node_x != '':
        node_x = args.node_x
if args.node_y:
    if args.node_y != '':
        node_y = args.node_y

if not pub:
    pub = input("What is your publish key?")
if not sub:
    sub = input("What is your subscribe key?")
if not node:
    node = input("What is your hostname?")
if not node_x:
    node_x = input("What is your X position in meters?")
if not node_y:
    node_y = input("What is your Y position in meters?")

scanner = ScanService(pub, sub, True, node, (node_x, node_y))
scanner.scan()
