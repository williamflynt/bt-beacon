import base64
import hashlib
import os
import pathlib
import socket
import sys

import psutil


def get_pn_uuid(set_uuid=True, override=False, uuid_key="PN_UUID"):
    if not override:
        uuid = os.getenv(uuid_key, None)
        if uuid is not None:
            return uuid

    ipv4_addr = socket.AddressFamily.AF_PACKET.value
    data = []
    # psutil returns a dict of interfaces with lists of addresses each
    for k, v in psutil.net_if_addrs().items():
        data.extend(v)
    # Each address has a family from socket, like AF_INET6, AF_PACKET...
    macs = [addr.address for addr in data if
            addr.family.value == ipv4_addr and
            addr.address != "00:00:00:00:00:00"]
    hasher = hashlib.md5(":".join(sorted(macs)).encode("utf-8"))
    ending = base64.urlsafe_b64encode(hasher.digest()[0:10]) \
        .decode("utf-8") \
        .replace('=', '')
    # End result is something like:  vagrant-0d9IJ6spIhQA1Q
    uuid = "{}-{}".format(socket.gethostname(), ending)

    def write_uuid(filename, line):
        try:
            with open(filename, "a") as f:
                f.writelines(line)
            return 1
        except:
            return 0

    if set_uuid:
        export_line = "export {}={}\n".format(uuid_key, uuid)
        os.environ[uuid_key] = uuid  # non-persistent but cheap
        pypath = os.path.dirname(os.path.abspath(sys.executable))

        write_count = 0
        # Naive file-writing - doesn't check for existing value
        if os.path.isfile(os.path.join(pypath, "activate")):  # check for venv
            postactivate = os.path.join(pypath, 'postactivate')
            write_count += write_uuid(postactivate, export_line)

        bashrc = os.path.join(str(pathlib.Path.home()), ".bashrc")
        if os.path.isfile(bashrc):
            write_count += write_uuid(bashrc, export_line)

        if not write_count:
            sys.stderr.write('\x1b[1;33m' + "WARNING: " + '\x1b[0m')
            sys.stderr.write("Could not find suitable file "
                             "to write UUID. Skipping...\n")

    return uuid
