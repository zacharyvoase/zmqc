def test_pubsub(zmq_pub, cmd_dev):
    zmq_pub.bind()
    url = zmq_pub.url
    cmd_dev.start(["-r", "-c", "SUB", url])
    msgs = ["one", "two", "three"]
    zmq_pub.send(msgs)
    cmd_dev.terminate()
    outmsgs = cmd_dev.recv()
    assert len(outmsgs) == len(msgs)
    assert outmsgs == msgs

def test_pushpull(zmq_push, cmd_dev):
    zmq_push.bind()
    url = zmq_push.url
    cmd_dev.start(["-r", "-c", "PULL", url])
    msgs = ["one", "two", "three"]
    zmq_push.send(msgs)
    cmd_dev.terminate()
    outmsgs = cmd_dev.recv()
    assert len(outmsgs) == len(msgs)
    assert outmsgs == msgs
