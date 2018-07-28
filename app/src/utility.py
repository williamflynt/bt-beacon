import base64
from datetime import datetime, time
import hashlib
import logging
import os
import pathlib
import socket
import sys

import dotenv
import psutil
import pytz

UTC = pytz.timezone('UTC')

FILE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(FILE_DIR, "..", "..", "logs")
UTIL_LOG = os.path.join(LOG_DIR, 'utility.log')

logger = logging.getLogger('util')
logfile = logging.FileHandler(UTIL_LOG)
logger.addHandler(logfile)


def get_pn_uuid(set_uuid=True, override=False, uuid_key="PN_UUID"):
    logger.setLevel(logging.DEBUG)
    logfile.setLevel(logging.DEBUG)

    env = pathlib.Path(FILE_DIR, "..", "..", "pubnub.env")
    if env.exists():
        dotenv.load_dotenv(str(env.absolute()))

    logger.debug("Checking override")
    if not override:
        logger.debug("override==False; looking in environment")
        uuid = os.getenv(uuid_key, None)
        if uuid is not None:
            logger.debug("Found UUID {}".format(uuid))
            return uuid

    logger.debug("Calculating new UUID")
    logger.debug("Getting AddressFamily value")
    ipv4_addr = socket.AddressFamily.AF_PACKET.value
    data = []
    logger.debug("Getting all addresses with psutil")
    # psutil returns a dict of interfaces with lists of addresses each
    for k, v in psutil.net_if_addrs().items():
        data.extend(v)
    logger.debug("Sorting out MACs")
    # Each address has a family from socket, like AF_INET6, AF_PACKET...
    macs = [addr.address for addr in data if
            addr.family.value == ipv4_addr and
            addr.address != "00:00:00:00:00:00"]
    logger.debug("Hashing MAC list of length {}".format(len(macs)))
    hasher = hashlib.md5(":".join(sorted(macs)).encode("utf-8"))
    logger.debug("Converting to base64 and truncating and decoding and replacing = sign")
    ending = base64.urlsafe_b64encode(hasher.digest()[0:10]) \
        .decode("utf-8") \
        .replace('=', '')
    logger.debug("Getting hostname and joining strings")
    # End result is something like:  vagrant-0d9IJ6spIhQA1Q
    uuid = "{}-{}".format(socket.gethostname(), ending)
    logger.debug("New UUID is {}".format(uuid))

    def write_uuid(filename, line):
        logger.debug("Trying to write to {}".format(filename))
        try:
            with open(filename, "a") as f:
                f.writelines(line)
            logger.debug("Success")
            return 1
        except:
            logger.debug("Fail")
            return 0

    if set_uuid:
        export_line = "\nexport {}={}\n".format(uuid_key, uuid)
        logger.debug("Putting UUID in environ")
        os.environ[uuid_key] = uuid  # non-persistent but cheap
        logger.debug("Getting executable python path")
        pypath = os.path.dirname(os.path.abspath(sys.executable))

        logger.debug("Writing to various files...")
        write_count = 0
        # Naive file-writing - doesn't check for existing value
        logger.debug("Checking for venv")
        if os.path.isfile(os.path.join(pypath, "activate")):  # check for venv
            logger.debug("Venv found; adding UUID to postactivate")
            postactivate = os.path.join(pypath, 'postactivate')
            write_count += write_uuid(postactivate, export_line)

        logger.debug("Adding to ~/.bashrc")
        bashrc = os.path.join(str(pathlib.Path.home()), ".bashrc")
        if os.path.isfile(bashrc):
            logger.debug("Found .bashrc")
            write_count += write_uuid(bashrc, export_line)

        logger.debug("Adding to pubnub.env")
        env = os.path.join(FILE_DIR, "..", "..", "pubnub.env")
        if os.path.isfile(env):
            logger.debug("Found pubnub.env")
            write_count += write_uuid(env,
                                      "\n{}={}\n".format(uuid_key, uuid))

        logger.debug("Checking writes...")
        if not write_count:
            logger.debug("No writes!")
            sys.stderr.write('\x1b[1;33m' + "WARNING: " + '\x1b[0m')
            sys.stderr.write("Could not find suitable file "
                             "to write UUID. Skipping...\n")
        else:
            logger.debug("Written {} times".format(write_count))
    logger.debug("Returning UUID of {}".format(uuid))
    return uuid


def sloppy_smaller(dt0, dt1, tz=UTC):
    """
    Compare two datetime-esque objects. Both can be naive, aware, time only,
      full datetime, or mix and match the criteria.
    If dt0 is smaller or equal, return 0, else return 1.
    :param dt0: obj A datetime or time
    :param dt1: obj A datetime or time
    :return: int 0 or 1
    """
    times = 0
    datetimes = 0
    for obj in [dt0, dt1]:
        if isinstance(obj, datetime):
            datetimes += 1
        elif isinstance(obj, time):
            times += 1
        else:
            raise Exception("sloppy_smaller was passed an object of type {}".format(type(obj)))

    if times == 2:
        if dt0 <= dt1:
            return 0
        else:
            return 1
    elif datetimes == 2:
        ts0 = dt0.astimezone(tz).timestamp()
        ts1 = dt1.astimezone(tz).timestamp()
        if ts0 <= ts1:
            return 0
        else:
            return 1
    else:
        try:
            t0 = dt0.astimezone(UTC).time()
        except AttributeError:
            t0 = dt0
        try:
            t1 = dt1.astimezone(UTC).time()
        except AttributeError:
            t1 = dt1
        if t0 <= t1:
            return 0
        else:
            return 1
