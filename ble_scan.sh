#!/usr/bin/env bash

source ./venv/bin/activate
cd app/src
python3 scan.py ${PUB_KEY} ${SUB_KEY} ${HOSTNAME} ${NODE_X} ${NODE_Y}
