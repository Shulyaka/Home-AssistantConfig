#!/bin/ash

HASSUSER="homeassistant"
TOKEN="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJjOTYxZWFmMzhlOWY0MTA1OGIxZWU1ZWJlNzYxY2FiZiIsImlhdCI6MTYwMDg3MDUxNSwiZXhwIjoxOTE2MjMwNTE1fQ.9LgvYrV3-WvJpfLaoxxxK98OeC82YMliFgJ6R6XXCqs"
HOSTNAME="https://shulyaka.org.ru"
#HOSTNAME="http://127.0.0.1:8123"

test "$USER" != "$HASSUSER" && CMD="$0 $@" && exec su "$HASSUSER" -c "$CMD"

if [ "$1" == "restart" ]; then
	shift
	CMD="curl -X POST -H \"Authorization: Bearer $TOKEN\" -H \"Content-Type: application/json\" -d '{}' $HOSTNAME/api/services/homeassistant/restart"
else
	CMD="echo Done"
fi

echo "Upgrading system"
sudo apk update && sudo apk upgrade

echo "Updating /srv/homeassistant"
git -C /srv/homeassistant pull --ff-only
for submodule in /srv/homeassistant/.submodules/*
do
	echo "Updating $submodule"
	git -C $submodule pull --ff-only
done
LANG=C git -C /srv/homeassistant status | grep -q "no changes added to commit" && git -C /srv/homeassistant add /srv/homeassistant/.submodules && git -C /srv/homeassistant commit -m "update submodules" && git -C /srv/homeassistant push

echo "Updating homeassistant"
sudo pip3 install --upgrade --upgrade-strategy=eager six==`apk info py3-six|grep installed|sed -e 's/py3-six-\([0-9\.]*\).*/\1/'` pymysql wheel colorlog homeassistant $@ && /srv/homeassistant/check_config.sh && ash -c "$CMD"
