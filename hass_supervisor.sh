#!/bin/ash

PROG=$@

source /srv/homeassistant/bin/activate

trap 'kill -TERM "$CPID"' TERM
trap 'kill -INT "$CPID"' INT

RET=100
while [ $RET == 100 ]; do
  RET=137

  echo Running "$PROG"
  $PROG &
  CPID=$!

  while [ -n "$(ps | awk '{print $1; }' | grep $CPID)" ]; do
    wait $CPID
    RET=$?
  done

  echo Return code $RET
done

exit $RET
