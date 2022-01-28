#!/bin/ash

HASSUSER="homeassistant"
PYTHONUSERBASE=/srv/homeassistant/deps
PATH=$PYTHONUSERBASE/bin:$PATH

test "$USER" != "$HASSUSER" && CMD="$0 $@" && exec su "$HASSUSER" -c "$CMD"

export PYTHONUSERBASE PATH

exec python3 $@
