# run this script right after you cloned/forked the repo

which git-flow 2>/dev/null
has_gitflow=$?
if [ ${has_gitflow} -gt 0  -a ! -x /usr/lib/git-core/git-flow ]; then
  echo
  echo "*************************************"
  echo
  echo "You need gitflow to hack on salt"
  echo " - https://github.com/nvie/gitflow"
  echo " - aptitude install git-flow"
  echo
exit 1
fi

git checkout master
git remote add upstream https://github.com/saltstack/salt.git
git config push.default tracking          # only push the current branch
git config branch.autosetuprebase always  # we want a linear history

echo "Configuring gitflow for this repository..."
git flow init -d
echo
echo "gitflow has been setup successfully!"
echo "See Contribute section at https://github.com/saltstack/salt for further information"

git checkout develop
git push -u origin develop
