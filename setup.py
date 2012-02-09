#!/usr/bin/env python
# -*- coding: utf-8 -*-

from distribute_setup import use_setuptools
use_setuptools()

from setuptools import setup, find_packages
import os.path as p

VERSION = open(p.join(p.dirname(p.abspath(__file__)), 'VERSION')).read().strip()

setup(
    name='zmqc',
    version=VERSION,
    description=u'A small but powerful command-line interface to ØMQ.',
    author='Zachary Voase',
    author_email='z@zacharyvoase.com',
    url='http://github.com/zacharyvoase/zmqc',
    package_dir={'': 'lib'},
    py_modules=['zmqc'],
    install_requires=[
        'argparse>=1.2.1',
    ],
    entry_points={
        'console_scripts': [
            'zmqc = zmqc:main',
        ],
    },
)
