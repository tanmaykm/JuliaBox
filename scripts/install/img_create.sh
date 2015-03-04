#! /usr/bin/env bash
# Build or pull JuliaBox docker images

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
JBOX_DIR=`readlink -e ${DIR}/../..`

DOCKER_IMAGE=juliabox/juliabox
DOCKER_IMAGE_VER=$(grep "^# Version:" ${JBOX_DIR}/docker/IJulia/Dockerfile | cut -d":" -f2)

API_DOCKER_IMAGE=juliabox/juliaboxapi
API_DOCKER_IMAGE_VER=$(grep "^# Version:" ${JBOX_DIR}/docker/api/Dockerfile | cut -d":" -f2)

function build_docker_image {
    echo "Building docker image ${DOCKER_IMAGE}:${DOCKER_IMAGE_VER} ..."
    sudo docker build --rm=true -t ${DOCKER_IMAGE}:${DOCKER_IMAGE_VER} docker/IJulia/
    sudo docker tag -f ${DOCKER_IMAGE}:${DOCKER_IMAGE_VER} ${DOCKER_IMAGE}:latest
}

function build_api_docker_image {
    echo "Building docker image ${API_DOCKER_IMAGE}:${DOCKER_IMAGE_VER} ..."
    sudo docker build --rm=true -t ${API_DOCKER_IMAGE}:${API_DOCKER_IMAGE_VER} docker/api/
    sudo docker tag -f ${API_DOCKER_IMAGE}:${API_DOCKER_IMAGE_VER} ${API_DOCKER_IMAGE}:latest
}

function pull_docker_image {
    echo "Pulling docker image ${DOCKER_IMAGE}:${DOCKER_IMAGE_VER} ..."
    sudo docker pull tanmaykm/juliabox:${DOCKER_IMAGE_VER}
    sudo docker tag -f tanmaykm/juliabox:${DOCKER_IMAGE_VER} ${DOCKER_IMAGE}:${DOCKER_IMAGE_VER}
    sudo docker tag -f tanmaykm/juliabox:${DOCKER_IMAGE_VER} ${DOCKER_IMAGE}:latest
}

function pull_api_docker_image {
    echo "Pulling docker image ${API_DOCKER_IMAGE}:${DOCKER_IMAGE_VER} ..."
    sudo docker pull tanmaykm/juliaboxapi:${API_DOCKER_IMAGE_VER}
    sudo docker tag -f tanmaykm/juliaboxapi:${API_DOCKER_IMAGE_VER} ${API_DOCKER_IMAGE}:${API_DOCKER_IMAGE_VER}
    sudo docker tag -f tanmaykm/juliaboxapi:${API_DOCKER_IMAGE_VER} ${API_DOCKER_IMAGE}:latest
}

function make_user_home {
	${JBOX_DIR}/docker/mk_user_home.sh
}

if [ "$1" == "pull" ]
then
    pull_docker_image
    make_user_home
elif [ "$1" == "build" ]
then
    build_docker_image
    make_user_home
elif [ "$1" == "home" ]
then
    make_user_home
elif [ "$1" == "pullapi" ]
then
    pull_api_docker_image
elif [ "$1" == "buildapi" ]
then
    build_api_docker_image
else
    echo "Usage: img_create.sh <pull | build | home | pullapi | buildapi>"
fi

echo
echo "DONE!"
