#!/bin/ash

HASSUSER="homeassistant"
PYTHONUSERBASE=/srv/homeassistant/deps
PATH=$PYTHONUSERBASE/bin:$PATH

test "$USER" != "$HASSUSER" && CMD="$0 $@" && exec su "$HASSUSER" -c "$CMD"

export PYTHONUSERBASE PATH

COMMAND=$1
shift

exec pip3 $COMMAND --user --no-cache-dir --log /tmp/pip-log-${USER}.txt $@
