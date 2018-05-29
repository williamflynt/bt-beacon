# --- BASE NODE ---
FROM python:3.6-jessie as base
ARG pub_key
ARG sub_key

RUN test -n "$pub_key"
RUN test -n "$sub_key"

# --- SCAN NODE ---
FROM base as scan

ENV PUB_KEY=$pub_key
ENV SUB_KEY=$sub_key

COPY app/requirements.scan.txt /

RUN apt-get update
RUN apt-get -y install bluetooth bluez bluez-hcidump python-bluez python-numpy python3-dev libbluetooth-dev libcap2-bin
RUN pip install -r /requirements.scan.txt
RUN setcap 'cap_net_raw,cap_net_admin+eip' $(readlink -f $(which python))

COPY app/src /app
WORKDIR /app

CMD ["./scan.py", "$pub_key", "$sub_key"]


# -- FLASK APP ---
FROM base as flask

ENV SUB_KEY=$sub_key

COPY app/requirements.flask.txt /
COPY app/src /app

RUN pip install -r /requirements.flask.txt

WORKDIR /app

EXPOSE 5000

CMD ["flask", "run"]