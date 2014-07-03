import zmq
import pytest
from itertools import count
import time
import subprocess
import sys

class ZmqDevice(object):
    def __init__(self, zmqsock_type):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmqsock_type)
    def send(self, msgs):
        for msg in msgs:
            self.socket.send(msg)
    def bind(self):
        port = self.socket.bind_to_random_port("tcp://*")
        #self.socket.bind("tcp://*:9999")
        #port = 9999
        self.url = "tcp://localhost:{port}".format(port=port)
class CmdDevice(object):
    def __init__(self):
        self.cmd = ["python", "lib/zmqc.py"]

    def start(self, cmd):
        cmd = self.cmd + cmd
        self.p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        time.sleep(0.5)
    def send(self, msgs, sleep_between=0, sleep_after=0.5):
        for msg in msgs:
            self.p.stdin.write(msg + "\r\n")
            time.sleep(sleep_between)
        time.sleep(sleep_after)

    def recv(self):
        return [line.rstrip("\n\r") for line in self.p.stdout]

    def terminate(self):
        time.sleep(0.5)
        self.p.terminate()

@pytest.fixture()
def zmq_pub(request):
    return ZmqDevice(zmq.PUB)

@pytest.fixture()
def zmq_push(request):
    return ZmqDevice(zmq.PUSH)

@pytest.fixture()
def cmd_dev(request):
    return CmdDevice()
