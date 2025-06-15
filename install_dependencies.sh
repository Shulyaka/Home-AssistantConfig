#!/bin/ash

source /srv/homeassistant/bin/activate

HASSUSER="homeassistant"

test "$USER" != "$HASSUSER" && CMD="$0 $@" && exec su "$HASSUSER" -c "$CMD"

CONFIG=$(mktemp -d)
trap "rm -rf $CONFIG" EXIT 
cp /srv/homeassistant/*.yaml /srv/homeassistant/*.json $CONFIG
ln -s /srv/homeassistant/custom_components $CONFIG/
cat /srv/homeassistant/.storage/core.config_entries | tr '{,' '\n' | grep domain | sed -e 's/.*\"domain\": *"//' -e 's/\"/:/' | sort | uniq >> $CONFIG/configuration.yaml
hass --script check_config --config $CONFIG
