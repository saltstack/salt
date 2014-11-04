#!/bin/sh

#
# template script for installing lxc containers via a single tarball
#

# Detect use under userns (unsupported)
for arg in "$@"; do
    [ "$arg" = "--" ] && break
    if [ "$arg" = "--mapped-uid" -o "$arg" = "--mapped-gid" ]; then
        echo "This template can't be used for unprivileged containers." 1>&2
        echo "You may want to try the \"download\" template instead." 1>&2
        exit 1
    fi
done

# Make sure the usual locations are in PATH
export PATH=$PATH:/usr/sbin:/usr/bin:/sbin:/bin

# defaults
lxc_network_type="veth"
lxc_network_link="br0"
default_path="/var/lib/lxc"

deploy_tar() {
    if [ -f "${path}/config" ]
    then
        cp "${path}/config" "${path}/_orig_config"
    fi
    tar xvf ${imgtar} -C "${path}"

    # Set utsname
    sed -i '/lxc.utsname/d' "${path}/config"
    echo "lxc.utsname = ${name}" >> "${path}/config"

    # Set rootfs
    sed -i '/lxc.rootfs/d' "${path}/config"
    echo "lxc.rootfs = ${path}/rootfs" >> "${path}/config"

    # Set proper hostname in /etc/hostname if present
    if [ -f "${path}/rootfs/etc/hostname" ]
    then
        echo ${name} >"${path}/rootfs/etc/hostname"
    fi
}

usage() {
    cat <<EOF
usage:
    ${1} -n|--name=<container_name>
        [-P|--packages=<pkg1,pkg2,...>] [-p|--path=<path>] [-t|--network_type=<type>] [-l|--network_link=<link>] [-h|--help]
Mandatory args:
  -n,--name         container name, used to as an identifier for that container from now on
Optional args:
  -p,--path         path to where the container rootfs will be created, defaults to ${default_path}/rootfs. The container config will go under ${default_path} in that case
  -t,--network_type set container network interface type (${lxc_network_type})
  -l,--network_link set network link device (${lxc_network_link})
  -r,--root_passwd  set container root password
  -h,--help         print this help
EOF
    return 0
}

options=$(getopt -o hp:n:l:t:r:i: -l help,rootfs:,path:,name:,network_type:,network_link:,root_passwd:,imgtar: -- "${@}")
if [ ${?} -ne 0 ]; then
    usage $(basename ${0})
    exit 1
fi
eval set -- "${options}"

while true
do
    case "${1}" in
    -h|--help)          usage ${0} && exit 0;;
    -p|--path)          path=${2}; shift 2;;
    -n|--name)          name=${2}; shift 2;;
    --rootfs)           rootfs_path=${2}; shift 2;;
    -i|--imgtar)        imgtar=${2}; shift 2;;
    -t|--network_type)  lxc_network_type=${2}; shift 2;;
    -l|--network_link)  lxc_network_link=${2}; shift 2;;
    -r|--root_passwd)   root_passwd=${2}; shift 2;;
    --)             shift 1; break ;;
    *)              break ;;
    esac
done

if [ -z "${name}" ]; then
    echo "missing required 'name' parameter"
    exit 1
fi

if [ ! -e /sys/class/net/${lxc_network_link} ]; then
    echo "network link interface does not exist"
    exit 1
fi

if [ -z "${path}" ]; then
    path="${default_path}/${name}"
fi

if [ $(id -u) -ne 0 ]; then
    echo "This script should be run as 'root'"
    exit 1
fi

if [ -z "$rootfs_path" ]; then
    rootfs_path="${path}/rootfs"
fi
config_path="${default_path}/${name}"

revert() {
    echo "Interrupted, cleaning up"
    lxc-destroy -n "${name}"
    rm -rf "${path}/${name}"
    rm -rf "${default_path}/${name}"
    exit 1
}

trap revert SIGHUP SIGINT SIGTERM

# May need to configure the name in the config
#copy_configuration
#if [ ${?} -ne 0 ]; then
#    echo "failed to write configuration file"
#    rm -rf "${config_path}"
#    exit 1
#fi

mkdir -p "${rootfs_path}"
deploy_tar
if [ ${?} -ne 0 ]; then
    echo "failed to deploy tarball image"
    rm -rf "${config_path}" "${path}"
    exit 1
fi

if [ -n "${root_passwd}" ]; then
    echo "root:${root_passwd}" | chroot "${rootfs_path}" chpasswd
fi

echo "container config is ${config_path}/config"
