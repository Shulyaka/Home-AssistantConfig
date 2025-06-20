#!/bin/bash

source /srv/homeassistant/bin/activate

HASSUSER="homeassistant"
TOKEN="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJjOTYxZWFmMzhlOWY0MTA1OGIxZWU1ZWJlNzYxY2FiZiIsImlhdCI6MTYwMDg3MDUxNSwiZXhwIjoxOTE2MjMwNTE1fQ.9LgvYrV3-WvJpfLaoxxxK98OeC82YMliFgJ6R6XXCqs"
HOSTNAME="https://shulyaka.org.ru"
#HOSTNAME="http://127.0.0.1:8123"

test "$USER" != "$HASSUSER" && CMD="$0 $@" && exec su "$HASSUSER" -c "$CMD"

if [ "$1" == "restart" ]; then
	shift
	CMD="curl -s -X POST -H \"Authorization: Bearer $TOKEN\" -H \"Content-Type: application/json\" -d '{}' $HOSTNAME/api/services/homeassistant/restart"
else
	CMD="echo Done"
fi

date
#echo "Upgrading system"
#sudo apk update && sudo apk add --upgrade apk-tools && sudo apk upgrade

echo "Updating /srv/homeassistant"
git -C /srv/homeassistant pull --ff-only
#git -C /srv/homeassistant submodule update --remote 
for submodule in /srv/homeassistant/.submodules/*
do
	echo "Updating $submodule"
	git -C $submodule pull --ff-only
done
find /srv/homeassistant/.submodules/ -name \*.js -exec cp '{}' /srv/homeassistant/www/ \;
LANG=C git -C /srv/homeassistant status | grep -q "no changes added to commit" && git -C /srv/homeassistant add /srv/homeassistant/.submodules && git -C /srv/homeassistant commit -m "update submodules" && git -C /srv/homeassistant push

echo "Updating homeassistant"
#sudo pip3 install --upgrade --upgrade-strategy=eager six==`apk info py3-six|grep installed|sed -e 's/py3-six-\([0-9\.]*\).*/\1/'` packaging==`apk info py3-packaging|grep installed|sed -e 's/py3-packaging-\([0-9\.]*\).*/\1/'` colorlog homeassistant esphome mosportal $@ && /srv/homeassistant/check_config.sh && ash -c "$CMD"
#pip3 install --upgrade --upgrade-strategy=eager homeassistant $@ && pip3 install --upgrade --upgrade-strategy=eager -c /srv/homeassistant/lib/python3.12/site-packages/homeassistant/package_constraints.txt music_assistant $@ && /srv/homeassistant/install_dependencies.sh && /srv/homeassistant/check_config.sh && ash -c "$CMD"
pip3 install --upgrade --upgrade-strategy=eager homeassistant $@
#sed -e 's/av==[0-9]*\.[0-9]*\.[0-9]*/av==12.3.0/' -i /srv/homeassistant/lib/python3.12/site-packages/homeassistant/components/generic/manifest.json -i /srv/homeassistant/lib/python3.12/site-packages/homeassistant/components/stream/manifest.json -i /srv/homeassistant/lib/python3.12/site-packages/homeassistant/package_constraints.txt
pip3 install --upgrade --upgrade-strategy=eager -c /srv/homeassistant/lib/python3.13/site-packages/homeassistant/package_constraints.txt music_assistant zlib_ng isal $@
/srv/homeassistant/install_dependencies.sh && /srv/homeassistant/check_config.sh && bash -c "$CMD"

echo "Done"
