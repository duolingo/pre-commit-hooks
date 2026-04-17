#!/usr/bin/env bash
x=1
y=2
if [ $x -eq 1 ] \
  && [ $y -eq 2 ]; then
  echo 'Hello world'
  echo $x > /dev/null
fi
case "$x" in
  1) echo 'one' ;;
  *) echo 'other' ;;
esac
