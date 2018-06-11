#--- Base node with all app code
FROM python:3.6-jessie as base

ARG pub_key
ARG sub_key
RUN test -n "$pub_key"
RUN test -n "$sub_key"

COPY app /opt/bt-beacon/app


#--- Locator Node
FROM base as locator

ARG pub_key
ARG sub_key
ENV PUB_KEY=${pub_key}
ENV SUB_KEY=${sub_key}

WORKDIR /opt/bt-beacon/app
RUN pip install -r requirements.locate.txt

WORKDIR /opt/bt-beacon/app/src
ENTRYPOINT ["python", "locate.py"]


#--- Flask App Webserver
FROM locator as flask

ARG sub_key
ENV SUB_KEY=${sub_key}

WORKDIR /opt/bt-beacon/app
RUN pip install -r requirements.flask.txt

EXPOSE 5000
WORKDIR /opt/bt-beacon/app/src
ENTRYPOINT ["flask", "run", "--host=0.0.0.0"]