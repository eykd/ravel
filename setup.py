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
        'attrs<16.4',
        'awesome-slugify<1.7',
        'blinker<1.5',
        'click<6.7',
        'colorclass<2.3',
        'marshmallow<2.10',
        'parsimonious<0.8',
        'path.py<10.2',
        'pydash<3.5',
        'straight.plugin<1.5',
        'syml<0.3'
    ],
    entry_points = dict(
        console_scripts = [
            'ravel = ravel.cli:main',
        ]
    ),
)
