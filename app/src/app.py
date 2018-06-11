import os

import eventlet

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from eventlet import sleep

eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'thisisasecret!'
socketio = SocketIO(app, async_mode='eventlet')

try:
    SUB_KEY = os.environ['SUB_KEY']
except KeyError:
    SUB_KEY = "demo"


@app.route('/')
def base_page():
    return render_template('pubnub.html', sub_key=SUB_KEY)


@app.route('/websocketdemo')
def socket_demo():
    return render_template('main.html')


class Worker(object):
    switch = False
    unit_of_work = 0

    def __init__(self, socketio):
        """
        assign socketio object to emit
        """
        self.socketio = socketio
        self.switch = True

    def do_work(self):
        """
        do work and emit message
        """
        i = 0
        while self.switch:
            message_list = ['message{}'.format(i) for i in range(i + 1)]
            self.socketio.emit('scan_results', message_list)
            i += 1
            sleep(1)

    def stop(self):
        """
        stop the loop
        """
        self.switch = False


@socketio.on('connect')
def connect(*args, **kwargs):
    """
    connect
    """
    global worker
    worker = Worker(socketio)


@socketio.on('end')
def on_end(*args, **kwargs):
    """end the scan loop"""
    worker.stop()
    emit('ended')


@socketio.on('begin')
def on_begin(*args, **kwargs):
    """begin the scan loop"""
    emit('started')
    # notice that the method is not called - don't put braces after method name
    socketio.start_background_task(target=worker.do_work)


if __name__ == '__main__':
    socketio.run(app, debug=True, host="0.0.0.0")
