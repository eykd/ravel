#!/bin/sh
set -e
set -x
pytest \
    --failed-first \
    --exitfirst \
    --cov=ravel \
    --cov-branch \
    --disable-warnings \
    --no-cov-on-fail $@
