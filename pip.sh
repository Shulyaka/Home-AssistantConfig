#!/bin/bash

source /srv/homeassistant/bin/activate

HASSUSER="homeassistant"
test "$USER" != "$HASSUSER" && exec su "$HASSUSER" -c "$0 $@"

COMMAND=$1
shift

exec pip $COMMAND --no-cache-dir --log /tmp/pip-log-${USER}.txt "$@"
