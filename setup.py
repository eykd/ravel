# -*- coding: utf-8 -*-
from setuptools import setup

PROJECT_NAME = 'ravel'
VERSION = '0.1.dev0'

setup(
    name = PROJECT_NAME,
    version = VERSION,
    author = "David Eyk",
    author_email = "david.eyk@gmail.com",
    modules = [PROJECT_NAME],
    install_requires = [
        'parsimonious',
        'pydash',
        'straight.plugin',
    ],
    tests_require = [
        'nose',
        'ensure',
    ],
    test_suite = 'nose.collector',
)
