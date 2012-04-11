#!/usr/bin/env python
# zmqc: a small but powerful command-line interface to ZMQ.

## Usage:
# zmqc [-0] [-r | -w] (-b | -c) SOCK_TYPE [-o SOCK_OPT=VALUE...] address [address ...]

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
#
# echo "hello" | zmqc -c REQ 'tcp://127.0.0.1:4000'
#
#   Send the string "hello" through a REQ socket connected to localhost port
#   4000, print whatever you get back and finish. In this way, REQ sockets can
#   be used for a rudimentary form of RPC in shell scripts.
#
# coproc zmqc -b REP 'tcp://*:4000'
# tr -u '[a-z]' '[A-Z]' <&p >&p &
# echo "hello" | zmqc -c REQ 'tcp://127.0.0.1:4000'
#
#   First, start a ZeroMQ REP socket listening on port 4000. The 'coproc' shell
#   command runs this as a shell coprocess, which allows us to run the next
#   line, tr. This will read its input from the REP socket's output, translate
#   all lowercase characters to uppercase, and send them back to the REP
#   socket's input. This, again, is run in the background. Finally, connect a
#   REQ socket to that REP socket and send the string "hello" through it: you
#   should just see the string "HELLO" printed on stdout.

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
        "%(prog)s [-h] [-v] [-0] [-r | -w] (-b | -c)\n            "
        "SOCK_TYPE [-o SOCK_OPT=VALUE...]\n            "
        "address [address ...]",
    description="zmqc is a small but powerful command-line interface to "
    "ZeroMQ. It allows you to create a socket of a given type, bind or "
    "connect it to multiple addresses, set options on it, and receive or send "
    "messages over it using standard I/O, in the shell or in scripts.",
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
                    "lives forever in 'read' mode, or until the end of input "
                    "in 'write' mode.")

mode_group = parser.add_argument_group(
    title='Mode',
    description="Whether to read from or write to the socket. For PUB/SUB "
    "sockets, this option is invalid since the behavior will always be write "
    "and read respectively. For REQ/REP sockets, zmqc will alternate between "
    "reading and writing as part of the request/response cycle.")
mode = mode_group.add_mutually_exclusive_group(required=False)
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
    choices=('PUSH', 'PULL', 'PUB', 'SUB', 'REQ', 'REP', 'PAIR'), type=str.upper,
    help="Which type of socket to create. Must be one of 'PUSH', 'PULL', "
    "'PUB', 'SUB', 'REQ', 'REP' or 'PAIR'. See `man zmq_socket` for an "
    "explanation of the different types. 'DEALER' and 'ROUTER' sockets are "
    "currently unsupported.")

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
    elif args.mode is not None and args.sock_type in ('REQ', 'REP'):
        parser.error("Cannot choose a read/write mode with a %s socket" %
                     args.sock_type)
    elif args.mode is None and args.sock_type not in ('REQ', 'REP'):
        parser.error("one of the arguments -r/--read -w/--write is required")

    # We also have to work around the fact that 'required' mutually exclusive
    # groups are not enforced when you put them in an argument group other
    # than the top-level parser.
    if args.behavior is None:
        parser.error("one of the arguments -b/--bind -c/--connect is required")

    context = zmq.Context.instance()
    sock = context.socket(getattr(zmq, args.sock_type))

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

    # Bind or connect to the provided addresses.
    for address in args.addresses:
        getattr(sock, args.behavior)(address)

    # Live forever if no `-n` argument was given, otherwise die after a fixed
    # number of messages.
    if args.number is None:
        iterator = itertools.repeat(None)
    else:
        iterator = itertools.repeat(None, args.number)

    try:
        if args.sock_type == 'REQ':
            req_loop(iterator, sock, args.delimiter, sys.stdin, sys.stdout)
        elif args.sock_type == 'REP':
            rep_loop(iterator, sock, args.delimiter, sys.stdin, sys.stdout)
        elif args.mode == 'r':
            read_loop(iterator, sock, args.delimiter, sys.stdout)
        elif args.mode == 'w':
            write_loop(iterator, sock, args.delimiter, sys.stdin)
    except StopIteration:
        # StopIteration is a sentinel for end of input, iterator exhaustion
        # (that is, we've processed the maximum number of messages) or Ctrl-C.
        # All need to be handled in the same way.
        return
    finally:
        sock.close()


def req_loop(iterator, sock, delimiter, input, output):
    """Write/read interaction for a REQ socket."""

    for _ in iterator:
        write(sock, delimiter, input)
        read(sock, delimiter, output)


def rep_loop(iterator, sock, delimiter, input, output):
    """Read/write interaction for a REP socket."""

    for _ in iterator:
        read(sock, delimiter, output)
        write(sock, delimiter, input)


def read_loop(iterator, sock, delimiter, output):
    """Continously get messages from the socket and print them on output."""

    for _ in iterator:
        read(sock, delimiter, output)


def write_loop(iterator, sock, delimiter, input):
    """Continously get messages from input and send them through a socket."""

    for _ in iterator:
        write(sock, delimiter, input)


def read(sock, delimiter, output):
    """Read one message from a socket onto an output stream."""

    try:
        message = sock.recv()
        output.write(message + delimiter)
        output.flush()
    except KeyboardInterrupt:
        raise StopIteration
    except IOError, exc:
        if exc.errno == errno.EPIPE:
            raise StopIteration
        raise


def write(sock, delimiter, input):
    """Write one message from an input stream into a socket."""

    try:
        message = read_until_delimiter(input, delimiter)
        sock.send(message)
    except (KeyboardInterrupt, EOFError):
        raise StopIteration


if __name__ == '__main__':
    main()
