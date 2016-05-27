#!/usr/bin/env bash
clear
rm -f .coverage
./bin/green --quiet-stdout --run-coverage tests
RESULT=$?

RESET="\033[0m"
GREEN="\033[0;32m"
RED="\033[0;31m"

if [ $RESULT -eq 0 ]
then
    echo -e ${GREEN}OK${RESET}
else
    echo -e ${RED}FAILURE${RESET}
fi

# exit $RESULT
