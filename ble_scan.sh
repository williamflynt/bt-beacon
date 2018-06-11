#!/usr/bin/env bash

cd app/src
python3 scan.py ${PUB_KEY} ${SUB_KEY} ${HOSTNAME} 0 0
