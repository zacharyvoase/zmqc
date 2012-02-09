## zmqc

zmqc is a small but powerful command-line interface to [ØMQ][zmq]. It allows
you to create a socket of a given type, bind or connect it to multiple
addresses, set options on it, and receive or send messages over it using
standard I/O, in the shell or in scripts. It's useful for debugging and
experimenting with most possible network topologies.

  [zmq]: http://www.zeromq.org/

### Usage

    zmqc [-h] [-v] [-0] (-r | -w) (-b | -c) SOCK_TYPE [-o SOCK_OPT=VALUE...] address [address ...]

#### Mode

<dl>
  <dt>-r, --read</dt>
    <dd>Read messages from the socket onto stdout.</dd>

  <dt>-w, --write</dt>
    <dd>Write messages from stdin to the socket.</dd>
</dl>

#### Behavior

<dl>
  <dt>-b, --bind</dt>
    <dd>Bind to the specified address(es).</dd>
  <dt>-c, --connect</dt>
    <dd>Connect to the specified address(es).</dd>
</dl>

#### Socket Parameters

<dl>
  <dt>SOCK_TYPE</dt>
  <dd>
    Which type of socket to create. Must be one of `PUSH`, `PULL`, `PUB`, `SUB`
    or `PAIR`. See `man zmq_socket` for an explanation of the different types.
    `REQ`, `REP`, `DEALER` and `ROUTER` sockets are currently unsupported.
    **--read** mode is unsupported for PUB sockets, and **--write** mode is
    unsupported for `SUB` sockets.
  </dd>
  <dt>-o SOCK_OPT=VALUE, --option SOCK_OPT=VALUE</dt>
  <dd>
    Socket option names and values to set on the created socket. Consult `man
    zmq_setsockopt` for a comprehensive list of options. Note that you can
    safely omit the `ZMQ_` prefix from the option name. If the created socket
    is of type `SUB`, and no `SUBSCRIBE` options are given, the socket will
    automatically be subscribed to everything.
  </dd>
  <dt>address</dt>
  <dd>
    One or more addresses to bind/connect to. Must be in full ZMQ format (e.g.
    `tcp://<host>:<port>`)
  </dd>
</dt>


## Examples

    zmqc -rc SUB 'tcp://127.0.0.1:5000'

Subscribe to `tcp://127.0.0.1:5000`, reading messages from it and printing them
to the console. This will subscribe to all messages by default.

* * * *

    ls | zmqc -wb PUSH 'tcp://*:4000'

Send the name of every file in the current directory as a message from a PUSH
socket bound to port 4000 on all interfaces. Don't forget to quote the address
to avoid glob expansion.

* * * *

    zmqc -rc PULL 'tcp://127.0.0.1:5202' | tee $TTY | zmqc -wc PUSH 'tcp://127.0.0.1:5404'

Read messages coming from a PUSH socket bound to port 5202 (note that we're
connecting with a PULL socket), echo them to the active console, and forward
them to a PULL socket bound to port 5404 (so we're connecting with a PUSH).

* * * *

    zmqc -n 10 -0rb PULL 'tcp://*:4123' | xargs -0 grep 'pattern'

Bind to a PULL socket on port 4123, receive 10 messages from the socket
(with each message representing a filename), and grep the files for
`'pattern'`. The `-0` option means messages will be NULL-delimited rather
than separated by newlines, so that filenames with spaces in them are not
considered two separate arguments by xargs.


## (Un)license

This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or distribute this
software, either in source code form or as a compiled binary, for any purpose,
commercial or non-commercial, and by any means.

In jurisdictions that recognize copyright laws, the author or authors of this
software dedicate any and all copyright interest in the software to the public
domain. We make this dedication for the benefit of the public at large and to
the detriment of our heirs and successors. We intend this dedication to be an
overt act of relinquishment in perpetuity of all present and future rights to
this software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL THE
AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

For more information, please refer to <http://unlicense.org/>
