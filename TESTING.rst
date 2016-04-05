=======
Testing
=======

This document provides instructions and recipes for testing the code before
submitting.

The only required procedure is as follows:

1. Make sure, you have `tox` installed::

   $ pip install -U tox

2. Run all tests across all locally available python versions (currently only
   for py27) and set of `pyzmq` versions::

   $ tox

Make sure, all tests are passing.

If it runs in at least one python version, you may ignore the `ERROR:
pyXY: InterpreterNotFound: pythonX.Y` errors.

.. contents:: Table of contents

Concepts
========

The testing infrastructure built on top of set of tools, explained in this
section.

`py.test` - test runner
-----------------------
Test runner collects available tests, runs some or all of them, reports
problems and even allows jumping into command line debugger if you need it.

There are multiple test runners available, here we use pytest_.

.. _pytest: http://pytest.org/latest/

`pytest` is mostly installed by running `tox` (see below), but can be installed by::

    $ pip test pytest

After that, command `py.test` shall be available.

Tests are placed in `tests` subdirectory or subdirectories.

To run all tests in `tests` subdirectory, be a bit verbose and print possible
output printed to stdout by your testing code::

    $ py.test -sv tests

To run all tests defined in `tests/test_it.py`::

    $ py.test -sv tests/test_it.py

pytest_ allows running most tests written for `unittest`, `nose` and other testing frameworks.

pytest_ also allows writing test cases using so called fixtures, which allow
writing very readable modular test suites.

Another strong point of `pytest` is error reporting. Generated reports are very well readable.

"virtualenv" - isolated environment
-----------------------------------

Virtual environments, or "virtualenv" in short is a tool, allowing to run your
python code in isolated python environment. It has the advantage, that you may
safely install into it without spoiling global python environment or being
restricted by what is installed in the global environment.

`virtualenv` can be set up by means of various tools (virtualenv_, tox_,
virtualenvwrapper_, venv_ and others).

In our case, we rely on `tox` command to create well defined virtual
environment, which can be easily recreated, extended and activated.

For that reason, there is no reason to install virtualenv separately.

.. _virtualenv: https://virtualenv.pypa.io/en/latest/

.. _tox: https://testrun.org/tox/latest/

.. _virtualenvwrapper: http://virtualenvwrapper.readthedocs.org/en/latest/

.. _venv: https://docs.python.org/3/library/venv.html


`tox` - automate testing across multiple python versions
--------------------------------------------------------

Building and testing python code might be complex as it involves building
fresh version of tested package, installing it incl. dependencies, installing
packages needed for testing, running test. This all is often needed in multiple
python versions and preferably shall be done using virtual environments.

With tox_, you just jump into directory with `tox.ini` and run::

    $ tox

Recipes
=======

This section provides practical instructions for specific activities related to
testing and development.

Run all tests in all testing environment variants
-------------------------------------------------

.. note:: Usually, `tox` tests functionality egainst different python versions.
    `zmqc` runs (currently) only with Python 2.7, but uses `tox` to test
    against various versions of `pyzmq`.

The command::

    $ tox

Will run all tests in all configured environments.

Relevant environments are defined in `tox.ini` file.

.. warning:: **`tox` shall not be started in activated virtualenv.**
    If you run `tox` in activated virtualenv, you may experience strange
    results.


Run all tests against single testing environment
------------------------------------------------
First, check, what testing environments is `tox` configured to run for::

    $ tox -l
    py27-pyzmq2
    py27-pyzmq
    py27-pyzmq13
    py27-pyzmq14
    py27-pyzmq15

Assuming you want to run tests against latest version for `pyzmq` run::

    $ tox -e py27-pyzmq

Creating and recreating virtualenvs by `tox`
--------------------------------------------

Running `tox`, one or more virtualenvs are always created::

    $ tox -e py27-pyzmq15

Virtualenvs are by default located in `.tox` directory::

    $ ls .tox
    dist
    log
    py27-pyzmq13
    py27-pyzmq14
    py27-pyzmq15
    py27-pyzmq2

.. note:: Ignore the `dist` and `log` directories.

To activate virtualenv on Linux::

    $ source .tox/py27-pyzmq15/bin/activate

On MS Windows::

    $ source .tox/py27-pyzmq15/Scripts/activate

After you activate virtualenv, command prompt often stars showing name of the virtualenv, e.g.::

    (py27-pyzmq15) $

This is shell specific behaviour.

You may install new packages into activated environment::

    (py27-pyzmq15) $ pip install anotherpackage

To deactivate virtualenv::

    (py27-pyzmq15) $ deactivate

If you need to recreate the environment, you may either remove given directory,
or ask `tox` to recreate it::

    $ tox -e py27-pyzmq15 -r

Run all tests under one python version using `py.test`
------------------------------------------------------

First, create and activate virtualenv for your target python version (as described above).

Then run all the tests::

    (py27-pyzmq15) $ py.test -sv tests

See `pytest` help for more options (see e.g. `--pdb` which starts command line
debugger in case some test fails).


Run selected tests under one python version using `py.test`
-----------------------------------------------------------

First, create and activate virtualenv for your target python version (as described above).

Then run the test of your interest::

    (py27-pyzmq15) $ py.test -sv tests/test_it.py

For more methods of selecting tests see: `Specifying tests / selecting tests`_

.. _`Specifying tests / selecting tests`: https://pytest.org/latest/usage.html#specifying-tests-selecting-tests
