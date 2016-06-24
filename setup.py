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
        'click==6.6',
        'parsimonious==0.6.2',
        'pydash==3.4.1',
        'straight.plugin==1.4.1',
        'awesome-slugify==1.6.5',
    ],
    entry_points = dict(
        console_scripts = [
            'ravel = ravel.cli:main',
        ]
    ),
)
