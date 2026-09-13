#!/bin/sh
set -e
set -x
exec uv run pytest \
    --failed-first \
    --exitfirst \
    --cov=ravel \
    --cov-branch \
    --disable-warnings \
    --no-cov-on-fail "$@"
