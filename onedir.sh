#!/bin/sh
#
#
# Script for making a onedir build. Requires Docker
#
#

SCRIPT=$(cat <<'EOF'
set -e
yum install deltarpm
yum install epel-release -y
yum --disablerepo="*" --enablerepo="epel" list available
yum install yum-utils -y
yum repolist
yum makecache
yum groupinstall "Development Tools" -y
yum-builddep python3 -y
yum install -y zlib-devel
yum install patchelf -y
cd salt
make salt.tar.xz
EOF
)

docker run --mount type=bind,source="$(pwd)",target=/salt --name onedir centos:centos7 /bin/bash  -c "$SCRIPT"
#docker cp onedir:salt/salt.tar.xz .
docker container rm onedir
