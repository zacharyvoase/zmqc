#!/usr/bin/env python
# zmqc: a small but powerful command-line interface to ZMQ.

## Usage:
# zmqc [-0] (-r | -w) (-b | -c) SOCK_TYPE [-o SOCK_OPT=VALUE...] address [address ...]

## Examples:
# zmqc -rc SUB 'tcp://127.0.0.1:5000'
#
#   Subscribe to 'tcp://127.0.0.1:5000', reading messages from it and printing
#   them to the console. This will subscribe to all messages by default.
#
# ls | zmqc -wb PUSH 'tcp://*:4000'
#
#   Send the name of every file in the current directory as a message from a
#   PUSH socket bound to port 4000 on all interfaces. Don't forget to quote the
#   address to avoid glob expansion.
#
# zmqc -rc PULL 'tcp://127.0.0.1:5202' | tee $TTY | zmqc -wc PUSH 'tcp://127.0.0.1:5404'
#
#   Read messages coming from a PUSH socket bound to port 5202 (note that we're
#   connecting with a PULL socket), echo them to the active console, and
#   forward them to a PULL socket bound to port 5404 (so we're connecting with
#   a PUSH).
#
# zmqc -n 10 -0rb PULL 'tcp://*:4123' | xargs -0 grep 'pattern'
#
#   Bind to a PULL socket on port 4123, receive 10 messages from the socket
#   (with each message representing a filename), and grep the files for
#   `'pattern'`. The `-0` option means messages will be NULL-delimited rather
#   than separated by newlines, so that filenames with spaces in them are not
#   considered two separate arguments by xargs.

## License:
# This is free and unencumbered software released into the public domain.
#
# Anyone is free to copy, modify, publish, use, compile, sell, or
# distribute this software, either in source code form or as a compiled
# binary, for any purpose, commercial or non-commercial, and by any
# means.
#
# In jurisdictions that recognize copyright laws, the author or authors
# of this software dedicate any and all copyright interest in the
# software to the public domain. We make this dedication for the benefit
# of the public at large and to the detriment of our heirs and
# successors. We intend this dedication to be an overt act of
# relinquishment in perpetuity of all present and future rights to this
# software under copyright law.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.

# For more information, please refer to <http://unlicense.org/>


import argparse
import array
import errno
import itertools
import re
import sys

import zmq


__version__ = '0.0.1'


class ParserError(Exception):
    """An exception which occurred when parsing command-line arguments."""
    pass


parser = argparse.ArgumentParser(
    prog='zmqc', version=__version__,
    usage=
        "%(prog)s [-h] [-v] [-0] (-r | -w) (-b | -c)\n            "
        "SOCK_TYPE [-o SOCK_OPT=VALUE...]\n            "
        "address [address ...]",
    description="zmqc is a small but powerful command-line interface to ZMQ. "
    "It allows you to create a socket of a given type, bind or connect it to "
    "multiple addresses, set options on it, and receive or send messages over "
    "it using standard I/O, in the shell or in scripts.",
    epilog="This is free and unencumbered software released into the public "
    "domain. For more information, please refer to <http://unlicense.org>.",
)

parser.add_argument('-0',
                    dest='delimiter', action='store_const',
                    const='\x00', default='\n',
                    help="Separate messages on input/output should be "
                    "delimited by NULL characters (instead of newlines). Use "
                    "this if your messages may contain newlines, and you want "
                    "to avoid ambiguous message borders.")

parser.add_argument('-n', metavar='NUM',
                    dest='number', type=int, default=None,
                    help="Receive/send only NUM messages. By default, zmqc "
                    "lives forever in 'write' mode, or until the end of input "
                    "in 'read' mode.")

mode_group = parser.add_argument_group(title='Mode')
mode = mode_group.add_mutually_exclusive_group(required=True)
mode.add_argument('-r', '--read',
                  dest='mode', action='store_const', const='r',
                  help="Read messages from the socket onto stdout.")
mode.add_argument('-w', '--write',
                  dest='mode', action='store_const', const='w',
                  help="Write messages from stdin to the socket.")

behavior_group = parser.add_argument_group(title='Behavior')
behavior = behavior_group.add_mutually_exclusive_group(required=True)
behavior.add_argument('-b', '--bind',
                      dest='behavior', action='store_const', const='bind',
                      help="Bind to the specified address(es).")
behavior.add_argument('-c', '--connect',
                      dest='behavior', action='store_const', const='connect',
                      help="Connect to the specified address(es).")

sock_params = parser.add_argument_group(title='Socket parameters')
sock_type = sock_params.add_argument('sock_type', metavar='SOCK_TYPE',
    choices=('PUSH', 'PULL', 'PUB', 'SUB', 'PAIR'), type=str.upper,
    help="Which type of socket to create. Must be one of 'PUSH', 'PULL', "
    "'PUB', 'SUB' or 'PAIR'. See `man zmq_socket` for an explanation of the "
    "different types. 'REQ', 'REP', 'DEALER' and 'ROUTER' sockets are "
    "currently unsupported. --read mode is unsupported for PUB sockets, and "
    "--write mode is unsupported for SUB sockets.")

sock_opts = sock_params.add_argument('-o', '--option',
    metavar='SOCK_OPT=VALUE', dest='sock_opts', action='append', default=[],
    help="Socket option names and values to set on the created socket. "
    "Consult `man zmq_setsockopt` for a comprehensive list of options. Note "
    "that you can safely omit the 'ZMQ_' prefix from the option name. If the "
    "created socket is of type 'SUB', and no 'SUBSCRIBE' options are given, "
    "the socket will automatically be subscribed to everything.")

addresses = sock_params.add_argument('addresses', nargs='+', metavar='address',
    help="One or more addresses to bind/connect to. Must be in full ZMQ "
    "format (e.g. 'tcp://<host>:<port>')")


def read_until_delimiter(stream, delimiter):

    """
    Read from a stream until a given delimiter or EOF, or raise EOFError.

        >>> io = StringIO("abcXdefgXfoo")
        >>> read_until_delimiter(io, "X")
        "abc"
        >>> read_until_delimiter(io, "X")
        "defg"
        >>> read_until_delimiter(io, "X")
        "foo"
        >>> read_until_delimiter(io, "X")
        Traceback (most recent call last):
        ...
        EOFError
    """

    output = array.array('c')
    c = stream.read(1)
    while c and c != delimiter:
        output.append(c)
        c = stream.read(1)
    if not (c or output):
        raise EOFError
    return output.tostring()


def get_sockopts(sock_opts):

    """
    Turn a list of 'OPT=VALUE' into a list of (opt_code, value).

    Work on byte string options:

        >>> get_sockopts(['SUBSCRIBE=', 'SUBSCRIBE=abc'])
        [(6, ''), (6, 'abc')]

    Automatically convert integer options to integers:

        >>> zmqc.get_sockopts(['LINGER=0', 'LINGER=-1', 'LINGER=50'])
        [(17, 0), (17, -1), (17, 50)]

    Spew on invalid input:

        >>> zmqc.get_sockopts(['LINGER=foo'])
        Traceback (most recent call last):
        ...
        zmqc.ParserError: Invalid value for option LINGER: 'foo'

        >>> zmqc.get_sockopts(['NONEXISTENTOPTION=blah'])
        Traceback (most recent call last):
        ...
        zmqc.ParserError: Unrecognised socket option: 'NONEXISTENTOPTION'

    """

    option_coerce = {
        int: set(zmq.core.constants.int_sockopts).union(
            zmq.core.constants.int64_sockopts),
        str: set(zmq.core.constants.bytes_sockopts)
    }

    options = []
    for option in sock_opts:
        match = re.match(r'^([A-Z_]+)\=(.*)$', option)
        if not match:
            raise ParserError("Invalid option spec: %r" % match)

        opt_name = match.group(1)
        if opt_name.startswith('ZMQ_'):
            opt_name = opt_name[4:]
        try:
            opt_code = getattr(zmq.core.constants, opt_name.upper())
        except AttributeError:
            raise ParserError("Unrecognised socket option: %r" % (
                match.group(1),))

        opt_value = match.group(2)
        for converter, opt_codes in option_coerce.iteritems():
            if opt_code in opt_codes:
                try:
                    opt_value = converter(opt_value)
                except (TypeError, ValueError):
                    raise ParserError("Invalid value for option %s: %r" % (
                        opt_name, opt_value))
                break
        options.append((opt_code, opt_value))
    return options


def main():
    args = parser.parse_args()

    # Do some initial validation which is more complex than what can be
    # specified in the argument parser alone.
    if args.sock_type == 'SUB' and args.mode == 'w':
        parser.error("Cannot write to a SUB socket")
    elif args.sock_type == 'PUB' and args.mode == 'r':
        parser.error("Cannot read from a PUB socket")

    context = zmq.Context.instance()
    sock = context.socket(getattr(zmq, args.sock_type))

    # Bind or connect to the provided addresses.
    for address in args.addresses:
        getattr(sock, args.behavior)(address)

    # Set any specified socket options.
    try:
        sock_opts = get_sockopts(args.sock_opts)
    except ParserError, exc:
        parser.error(str(exc))
    else:
        for opt_code, opt_value in sock_opts:
            sock.setsockopt(opt_code, opt_value)

        # If we have a 'SUB' socket that's not explicitly subscribed to
        # anything, subscribe it to everything.
        if (sock.socket_type == zmq.SUB and
            not any(opt_code == zmq.SUBSCRIBE
                    for (opt_code, _) in sock_opts)):
            sock.setsockopt(zmq.SUBSCRIBE, '')

    # Live forever if no `-n` argument was given, otherwise die after a fixed
    # number of messages.
    if args.number is None:
        iterator = itertools.repeat(None)
    else:
        iterator = itertools.repeat(None, args.number)

    try:
        if args.mode == 'r':
            read_loop(iterator, sock, args.delimiter, sys.stdout)
        elif args.mode == 'w':
            write_loop(iterator, sock, args.delimiter, sys.stdin)
    finally:
        sock.close()


def read_loop(iterator, sock, delimiter, output):
    """Continously get messages from the socket and print them on output."""

    for _ in iterator:
        try:
            message = sock.recv()
            output.write(message + delimiter)
            output.flush()
        except KeyboardInterrupt:
            return
        except IOError, exc:
            if exc.errno == errno.EPIPE:
                return
            raise


def write_loop(iterator, sock, delimiter, input):
    """Continously get messages from input and send them through the socket."""

    for _ in iterator:
        try:
            message = read_until_delimiter(input, delimiter)
            sock.send(message)
        except (KeyboardInterrupt, EOFError):
            return


if __name__ == '__main__':
    main()
