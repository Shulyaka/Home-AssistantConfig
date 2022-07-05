#!/bin/ash

PROG=$@

RET=100
while [ $RET == 100 ]; do
  echo Running "$PROG"
  $PROG
  RET=$?
  echo Return code $RET
done

exit $RET
