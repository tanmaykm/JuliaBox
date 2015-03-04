#! /usr/bin/env bash
# Start JuliaAPIBox server

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
JBOX_DIR=`readlink -e ${DIR}/../../..`

source ${DIR}/../../jboxcommon.sh

cp_tornado_userconf

sudo supervisord -c ${JBOX_DIR}/host/jbapi_supervisord.conf
sudo supervisorctl -c ${JBOX_DIR}/host/jbapi_supervisord.conf start all
