# BT-Beacon - Track BLE Beacons

A Python package for tracking Bluetooth Low Energy beacons using multilateralization.

BT-Beacon also includes Dockerfiles and tools for quickly setting up your containerized deployment.

The project is designed around receiver nodes and a server node. 

Receivers collect signals from the surrounding beacons, and publish the data to a streaming datastore (like PubNub or 
networked Kafka instance). 

The server node performs the location process and pushes data to a relational database. 

The server node also runs a small webserver for node configuration, and real time visualization of data. 

## Getting Started

These instructions will give you a copy of the project up and running on your local machine for development and testing
purposes. See deployment for notes on how to deploy the project on a live system.

### Requirements

This project is tested on Raspbian Stretch kernel 4.1.4 (2018-04-18), and will probably work on most Linux versions with
Bluetooth Low Energy support (ex: Ubuntu Core). It runs on Raspberry Pi 3B+.

You also need Python 3.x - some functionality may not work with Python 2. This project was created and tested with 
Python 3.6.

Finally, you will need Docker CE. You can find out more at the [Docker website](https://www.docker.com).

### Installing

Connect to your Raspberry Pi with ssh. Default user is `pi`, and default password is `raspberry`.

<aside class="notice">
Some distros (like Ubuntu) use a `nosuid` option when mounting home directories. That option disables the capabilities
we assign using `setcap` below, which means we can only get full functionality with `sudo python`. To use this package
with those distros make sure the virtual environment is in a non-user folder, like `/home/devel/bt-beacon`. 
</aside>

To get started, you need to install some system packages:

```
sudo apt-get -y install bluez bluez-hcidump
sudo apt-get -y install python3-dev libbluetooth-dev libcap2-bin
# Give python the required socket permissions
sudo setcap 'cap_net_raw,cap_net_admin+eip' $(readlink -f $(which python))
```

You'll also need a virtual environment (recomended) with some Python packages:

```
pip install -r app/requirements.txt
```

Now you can run a scan!

~~~
# Do the scan
~~~

## Running the tests

There aren't any automated tests for this package yet! Underlying requirements (`requirements.txt`) have tests, and you 
can refer to those pages on GitHub [here](https://www.github.com) and [here](https://www.github.com).

## Usage

Here is some basic usage info to get you off the ground. Maybe even a simple application.

### Receiver Nodes

The receivers are physical machines with BLE capability. They listen for beacons and publish the data to the server
node for processing.

### Server Node

The server node runs the streaming datastore (Apache Pulsar, PubNub) and processes the streams. It does the heavy
lifting of multilateralization and relational database management. You can run it on a receiver node, or use a 
dedicated machine or VM.

## Deployment

To deploy this project for testing or real application, you can use the Docker configuration files. This deploys
preconfigured containers for instant functionality!

```
Docker commands here
```

If you prefer to build from scratch, try this:

```
Build from scratch here
```

## Built With

* [Dropwizard](http://www.dropwizard.io/1.0.2/docs/) - The web framework used
* [Maven](https://maven.apache.org/) - Dependency Management
* [ROME](https://rometools.github.io/rome/) - Used to generate RSS Feeds

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details

## Acknowledgments

* Hat tip to anyone who's code was used
* Inspiration
* etc

