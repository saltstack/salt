#!/bin/sh

HERE=$(dirname $0)
TOP=$(cd $HERE/.. ; pwd)
OUTPUT=$HERE/output
GZ_SMF=/opt/custom/smf
MASTER=$1

# process the manifests
mkdir $OUTPUT
for file in $HERE/*.xml
do
  sed "s#SALT_PREFIX#$TOP#" <$file >$OUTPUT/$(basename $file)
done

# detect global or non-global zone
if [[ $(zonename) == global ]]
then
  # we assume global zones are always minions only
  # and we assume that they want to have the service come back on reboot
  mkdir -p $GZ_SMF
  sed 's/false/true/' < $OUTPUT/salt-minion.xml > $GZ_SMF/salt-minion.xml
  svccfg import $OUTPUT/salt-minion.xml
  echo "Minion is set to be launched at boot"
else
  # non global zones get all three services imported
  # and the user can enable whichever ones they want
  for file in $OUTPUT/*.xml
  do
    svccfg import $file
  done
  echo "To enable master service, invoke either of"
  echo "    svcadm enable salt-master"
  echo "    svcadm enable salt-syndic"
  echo "as appropriate"
fi

# if the user provided the name of the master as an argument
# configure a minimal minion file and start the minion
if [[ -n $MASTER ]]
then
  [[ -f $TOP/etc/minion.example ]] || mv $TOP/etc/minion{,.example}
  echo "master: $MASTER" > $TOP/etc/minion
  echo "Minion configured to talk to master $MASTER. Enabling minion now."
  svcadm enable salt-minion
else
  echo "To enable minion service, invoke:"
  echo "    svcadm enable salt-minion"
fi

rm -rf $OUTPUT
