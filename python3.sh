#!/bin/bash

source /srv/homeassistant/bin/activate

HASSUSER="homeassistant"
test "$USER" != "$HASSUSER" && CMD="$0 $@" && exec su "$HASSUSER" -c "$CMD"

exec python3 $@
