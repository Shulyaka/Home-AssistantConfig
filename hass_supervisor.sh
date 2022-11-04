#!/bin/ash

PROG=$@

trap 'kill -TERM "$CPID"' TERM
trap 'kill -INT "$CPID"' INT

RET=100
while [ $RET == 100 ]; do
  echo Running "$PROG"

  $PROG &
  CPID=$!

  RET=129
  while [ $RET -gt 128 ]; do
    wait $CPID
    RET=$?
  done

  echo Return code $RET
done

exit $RET
