#! /usr/bin/env bash
# Stop JuliaAPIBox server

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
JBOX_DIR=`readlink -e ${DIR}/../../..`

sudo supervisorctl -c ${JBOX_DIR}/host/jbapi_supervisord.conf stop all
sudo supervisorctl -c ${JBOX_DIR}/host/jbapi_supervisord.conf shutdown
