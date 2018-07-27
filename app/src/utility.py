import base64
import hashlib
import logging
import os
import pathlib
import socket
import sys

import psutil

FILE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(FILE_DIR, "..", "..", "logs")
UTIL_LOG = os.path.join(LOG_DIR, 'utility.log')


def get_pn_uuid(set_uuid=True, override=False, uuid_key="PN_UUID"):
    logging.basicConfig(filename=UTIL_LOG, level=logging.DEBUG)

    logging.debug("Checking override")
    if not override:
        logging.debug("override==False; looking in environment")
        uuid = os.getenv(uuid_key, None)
        if uuid is not None:
            logging.debug("Found UUID {}".format(uuid))
            return uuid

    logging.debug("Calculating new UUID")
    logging.debug("Getting AddressFamily value")
    ipv4_addr = socket.AddressFamily.AF_PACKET.value
    data = []
    logging.debug("Getting all addresses with psutil")
    # psutil returns a dict of interfaces with lists of addresses each
    for k, v in psutil.net_if_addrs().items():
        data.extend(v)
    logging.debug("Sorting out MACs")
    # Each address has a family from socket, like AF_INET6, AF_PACKET...
    macs = [addr.address for addr in data if
            addr.family.value == ipv4_addr and
            addr.address != "00:00:00:00:00:00"]
    logging.debug("Hashing MAC list of length {}".format(len(macs)))
    hasher = hashlib.md5(":".join(sorted(macs)).encode("utf-8"))
    logging.debug("Converting to base64 and truncating and decoding and replacing = sign")
    ending = base64.urlsafe_b64encode(hasher.digest()[0:10]) \
        .decode("utf-8") \
        .replace('=', '')
    logging.debug("Getting hostname and joining strings")
    # End result is something like:  vagrant-0d9IJ6spIhQA1Q
    uuid = "{}-{}".format(socket.gethostname(), ending)
    logging.debug("New UUID is {}".format(uuid))

    def write_uuid(filename, line):
        logging.debug("Trying to write to {}".format(filename))
        try:
            with open(filename, "a") as f:
                f.writelines(line)
            logging.debug("Success")
            return 1
        except:
            logging.debug("Fail")
            return 0

    if set_uuid:
        export_line = "export {}={}\n".format(uuid_key, uuid)
        logging.debug("Putting UUID in environ")
        os.environ[uuid_key] = uuid  # non-persistent but cheap
        logging.debug("Getting executable python path")
        pypath = os.path.dirname(os.path.abspath(sys.executable))

        logging.debug("Writing to various files...")
        write_count = 0
        # Naive file-writing - doesn't check for existing value
        logging.debug("Checking for venv")
        if os.path.isfile(os.path.join(pypath, "activate")):  # check for venv
            logging.debug("Venv found; adding UUID to postactivate")
            postactivate = os.path.join(pypath, 'postactivate')
            write_count += write_uuid(postactivate, export_line)

        logging.debug("Adding to ~/.bashrc")
        bashrc = os.path.join(str(pathlib.Path.home()), ".bashrc")
        if os.path.isfile(bashrc):
            logging.debug("Found .bashrc")
            write_count += write_uuid(bashrc, export_line)

        logging.debug("Checking writes...")
        if not write_count:
            logging.debug("No writes!")
            sys.stderr.write('\x1b[1;33m' + "WARNING: " + '\x1b[0m')
            sys.stderr.write("Could not find suitable file "
                             "to write UUID. Skipping...\n")
        else:
            logging.debug("Written {} times".format(write_count))
    logging.debug("Returning UUID of {}".format(uuid))
    return uuid
