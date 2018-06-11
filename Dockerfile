#--- Base node with all app code
FROM python:3.6-jessie as base

ARG pub_key
ARG sub_key
RUN test -n "$pub_key"
RUN test -n "$sub_key"

COPY app /app


#--- Locator Node
FROM base as locator

ARG pub_key
ARG sub_key

WORKDIR /app
RUN pip install -r requirements.locate.txt

WORKDIR /app/src
ENTRYPOINT ["python", "locate.py", "${pub_key}", "${sub_key}"]


#--- Flask App Webserver
FROM locator as flask

ARG sub_key
ENV SUB_KEY=${sub_key}

WORKDIR /app
RUN pip install -r requirements.flask.txt

EXPOSE 5000
WORKDIR /app/src
CMD ["flask", "run"]