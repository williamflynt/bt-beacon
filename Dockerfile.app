FROM python:3.6-jessie

COPY app/requirements.txt /

RUN apt-get update
RUN apt-get -y install bluetooth bluez bluez-hcidump python-bluez python-numpy
RUN pip install -r /requirements.txt

COPY app/src /app
WORKDIR /app

EXPOSE 5000

ENTRYPOINT ["python"]
CMD ["app.py"]