#!/bin/bash
#
# onedir.sh
#
# Script for making a onedir build. Requires Docker
#
#
set +e

# XXX: centos 7 with dependencies installed, we need to figure out how we'll
# handle this
CONTAINER_IMAGE=dwoz1/cicd:onedir-centos7

CONTAINER_NAME="onedir-$RANDOM"
SOURCE_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
# If onedir.sh changes locations this needs to change
PROJECT_ROOT=$(dirname $SOURCE_DIR)
SCRIPT=$(cat <<EOF
set -e
cd /salt
make clean
make onedir
chown -R $UID salt*.tar.xz build
chgrp -R $UID salt*.tar.xz build
EOF
)
docker pull $CONTAINER_IMAGE
echo "Running $CONTAINER_NAME"
docker run \
  --mount type=bind,source="$PROJECT_ROOT",target=/salt \
  --name $CONTAINER_NAME \
  $CONTAINER_IMAGE \
  /bin/bash -c "$SCRIPT"
echo "Removing $CONTAINER_NAME"
docker container rm $CONTAINER_NAME
