#!/bin/bash

SCRIPTS=("salt" "salt-api" "salt-call" "salt-cloud" "salt-cp" "salt-key" "salt-master" "salt-minion" "salt-proxy" "salt-run" "salt-ssh" "salt-syndic" "spm")

mkdir -p /opt/saltstack/salt
cp -R lib bin /opt/saltstack/salt/

for script in ${SCRIPTS[@]}; do
    cp $script /usr/bin;
    sed -i -e '/#/ D; s/"exec".*/#!\/opt\/saltstack\/salt\/bin\/python3/g' /usr/bin/$script
done

