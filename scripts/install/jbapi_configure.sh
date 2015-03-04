#! /usr/bin/env bash
# Configure JuliaApiBox components

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
JBOX_DIR=`readlink -e ${DIR}/../..`

source ${DIR}/../jboxcommon.sh

DOCKER_IMAGE_PFX=juliabox/juliaboxapi
NUM_LOCALMAX=2

function usage {
  echo
  echo 'Usage: ./setup.sh optional_args'
  echo ' -n  <num>      : Maximum number of active containers. Default 2.'
  echo
  echo 'Post setup, additional configuration parameters may be set in jbox.user'
  echo 'Please see README.md (https://github.com/JuliaLang/JuliaBox) for more details '
  
  exit 1
}

function gen_sesskey {
    echo "Generating random session validation key"
    SESSKEY=`< /dev/urandom tr -dc _A-Z-a-z-0-9 | head -c32`
    echo $SESSKEY > .jbox_session_key
}

function configure_resty_tornado {
    echo "Setting up nginx.conf ..."
    sed  s/\$\$NGINX_USER/$USER/g $NGINX_CONF_DIR/jbapi_nginx.conf.tpl > $NGINX_CONF_DIR/jbapi_nginx.conf

    sed  -i s/\$\$SESSKEY/$SESSKEY/g $NGINX_CONF_DIR/jbapi_nginx.conf
    sed  s/\$\$SESSKEY/$SESSKEY/g $TORNADO_CONF_DIR/jbapi_tornado.conf.tpl > $TORNADO_CONF_DIR/jbapi_tornado.conf

    sed  -i s/\$\$NUM_LOCALMAX/$NUM_LOCALMAX/g $TORNADO_CONF_DIR/jbapi_tornado.conf
    sed  -i s,\$\$DOCKER_IMAGE_PFX,$DOCKER_IMAGE_PFX,g $TORNADO_CONF_DIR/jbapi_tornado.conf

    sed  s,\$\$JBOX_DIR,$JBOX_DIR,g host/juliabox_logrotate.conf.tpl > host/juliabox_logrotate.conf
}


while getopts  "n:" FLAG
do
  if test $FLAG == '?'
     then
        usage

  elif test $FLAG == 'n'
     then
        NUM_LOCALMAX=$OPTARG
  fi
done


if [ ! -e .jbox_session_key ]
then
    gen_sesskey
fi
SESSKEY=`cat .jbox_session_key`

configure_resty_tornado

echo
echo "DONE!"
 
