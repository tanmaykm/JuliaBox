#! /usr/bin/env bash
# Restart JuliaAPIBox server

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
JBOX_DIR=`readlink -e ${DIR}/../../..`

source ${DIR}/../../jboxcommon.sh

cp_tornado_userconf

sudo supervisorctl -c ${PWD}/host/jbapi_supervisord.conf restart all
