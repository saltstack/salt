#!/usr/bin/bash

# shellcheck disable=SC2001

gdescribe=$(git describe)
gversion=$(echo "${gdescribe}" | sed s/^v//)
xversion=$(echo "${gversion}" | sed s/-/+/)
new_version=$(echo "${xversion}" | sed s/-/./)
sed -i 's&REPLACE_WITH_VERSION&'"${new_version}"'&' setup.cfg
