# -*- coding: utf-8 -*-
from setuptools import setup

PROJECT_NAME = 'ravel'
VERSION = '0.1.dev0'

setup(
    name = PROJECT_NAME,
    version = VERSION,
    author = "David Eyk",
    author_email = "david@worldsenoughstudios.com",
    modules = [PROJECT_NAME],
    install_requires = [
        'attrs',
        'awesome-slugify',
        'blinker',
        'click',
        'colorclass',
        'marshmallow',
        'parsimonious',
        'path',
        'pydash',
        'straight.plugin',
        'strictyaml',
        'syml',
    ],
    entry_points = dict(
        console_scripts = [
            'ravel = ravel.cli:main',
        ]
    ),
)
