import zmq
import pytest
from itertools import count

def test_it():
    url = "tcp://147.32.102.103:9260"
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.setsockopt(zmq.SUBSCRIBE, "")
    socket.connect(url)
    for i in xrange(5):
        print socket.recv()


if __name__ == "__main__":
    test_it()
