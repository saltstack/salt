#!/bin/bash

SCRIPTS=("salt" "salt-api" "salt-call" "salt-cloud" "salt-cp" "salt-key" "salt-master" "salt-minion" "salt-proxy" "salt-run" "salt-ssh" "salt-syndic" "spm")

rm -rf /opt/saltstack/salt

for script in ${SCRIPTS[@]}; do
    rm /usr/bin/$script;
done
