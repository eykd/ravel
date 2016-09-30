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
        'attrs==16.2.0',
        'click==6.6',
        'marshmallow==2.9.0',
        'parsimonious==0.7.0',
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
