#!/bin/sh
set -e
set -x
pytest \
    --failed-first \
    --exitfirst \
    --cov=ravel \
    --cov-branch \
    --no-cov-on-fail $@
