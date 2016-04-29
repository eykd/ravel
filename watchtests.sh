#!/usr/bin/env bash
./bin/sniffer \
    -x --with-coverage \
    -x --cover-package=ravel \
    -x --cover-branches \
    -x --cover-inclusive \
    -x --cover-erase
