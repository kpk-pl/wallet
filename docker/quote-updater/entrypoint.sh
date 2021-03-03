#!/usr/bin/env sh
set -e

function sleep_until() {
  local difference=$(($(date -d "$1" +%s) - $(date +%s)))

  if [ $difference -lt 0 ] ; then
    difference=$((86400 + difference))
  fi

  echo "Sleeping $difference to $1" >&2
  sleep $difference
}

while true ; do
  sleep_until $QUOTE_UPDATER_SCHEDULE
  curl -X $QUOTE_UPDATER_METHOD $QUOTE_UPDATER_URI
done
