#!/bin/ash

HASSUSER="homeassistant"

test "$USER" != "$HASSUSER" && CMD="$0 $@" && exec su "$HASSUSER" -c "$CMD"

hass --script check_config --config /srv/homeassistant
