#!/usr/bin/env bash
./bin/nosetests \
    --with-coverage \
    --cover-package=ravel \
    --cover-branches \
    --cover-inclusive \
    --cover-erase
