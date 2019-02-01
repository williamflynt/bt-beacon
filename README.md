# BT Beacon

This package will locate BLE beacons using trilateration.


### Hardware

2+ Raspberry Pi (at least one running `locate.py` and `app.py`).

### Needed Components

You have to have all these things running to get this done: 

* BLE scanners (`./ble_scan.sh`)
* Locate node (`./locate.sh`)
* BLE scanners (`./run_flask.sh`)

### Setup & Install & Scan

From a fresh install of Raspbian (search Etcher):

1. Ensure you place the `ssh` and `wpa_supplicant` file in the boot partition
2. Clone the repo into `/opt`:
3. Run `./ble_scan_setup.sh`
4. Set your `PUB_KEY` and `SUB_KEY` for PubNub using code below.
5. Set your `NODE_X` and `NODE_Y` using code below. You can also use the 
`ble_placement` server on `0.0.0.0:8765`.
6. Run `./ble_scan.sh`

This code is to help you! These are the steps you should take.
```bash
cd /opt
sudo git clone https://github.com/williamflynt/bt-beacon.git
sudo chown pi:pi -R ./bt-beacon
cd ./bt-beacon
./ble_scan_setup.sh
```
And then...
```bash
export PUB_KEY="pubkey"
export SUB_KEY="subkey"
export NODE_X=3
export NODE_Y=3
echo "export PUB_KEY=${PUB_KEY}" >> ~/.bashrc
echo "export SUB_KEY=${SUB_KEY}" >> ~/.bashrc
echo "export NODE_X=${NODE_X}" >> ~/.bashrc
echo "export NODE_Y=${NODE_Y}" >> ~/.bashrc
echo "export PUB_KEY=${PUB_KEY}" >> /opt/bt-beacon/venv/bin/activate
echo "export SUB_KEY=${SUB_KEY}" >> /opt/bt-beacon/venv/bin/activate
echo "export NODE_X=${NODE_X}" >> /opt/bt-beacon/venv/bin/activate
echo "export NODE_Y=${NODE_Y}" >> /opt/bt-beacon/venv/bin/activate
```

### Location Service & Viewing Data

I like to do this from a laptop.

##### Setup location service

1. `python locate.py ${PUB_KEY} ${SUB_KEY}`

##### Run Web UI

1. `./run_flask.sh`

If you want to add a little bit of extra help to locating your beacons, you can also 
run `./ble_scan.sh` from your laptop, but you should be stationary!


### What about these `node` files?

I don't know. I don't remember.