====================
Salt Release Process
====================

The goal for Salt projects is to cut a new feature release every three to
four months. This document outlines the process for these releases, and the
subsequent bug fix releases which follow.


Feature Release Process
=======================

When a new release is ready to be cut, the person responsible for cutting the
release will follow the following steps (written using the 3000 release as an
example):

#. Create first public draft of release notes with major features.
#. Remove any deprecations for the upcoming release.
#. Ensure all required features are merged.
#. Create issue to start the process of deprecating for the next feature release.
#. Run through a manual test run based off of the head of the feature branch.
#. Update all name references to version number in the docs. For example
   all neon references in the docs needs to be moved to v3000
#. Review the release notes with major features.
#. Generate the new man pages for the release.
#. Create internal RC tag for testing from the head of the master branch.
#. Build latest windows, mac, ubuntu, debian and redhat packages.
#. Run manual and package tests against new RC packages.
#. Push the internal tag live to salt's repo.
#. Publish release archive to pypi based off tag.
#. Push the RC packages live.
#. Announce new RC to salt-users and salt-announce google groups.
#. Triage incoming issues based on the new RC release.
#. Fix RC issues once they are categorized as a release blocker.
#. Depending on the issues found during the RC process make a decision
   on whether to release based off the RC or go through another RC process
#. If a RC is categorized as stable, build all required packages.
#. Test all release packages.
#. Test links from `repo.saltproject.io`_.
#. Update installation instructions with new release number at `repo.saltproject.io`_.
#. Review and update all impacted :ref:`installation` documentation.
#. Update and build docs to include new version (3000) as the latest.
#. Pre-announce on salt-users google group that we are about to update our repo.
#. Publish release (v3000) archive to pypi based off tag.
#. Publish all packages live to repo.
#. Publish the docs.
#. Create release at `github`_
#. Update win-repo-ng with new salt versions.
#. Announce release is live to irc, salt-users, salt-announce and release slack
   community channel.


Bugfix Releases
===============

Once a feature release branch has been cut from the ``master`` branch, if
serious bugs or a CVE is found for the most recent release a bugfix release
will need to be cut. A temporary branch will be created based off of the previous
release tag. For example, if it is determined that a 3000.1 release needs to occur
a 3000.1 branch will be created based off of the v3000 tag. The fixes that need
to go into 3000.1 will be added and merged into this branch. Here are the steps
for a bugfix release.

#. Ensure all required bug fixes are merged.
#. Create release branch with the version of the release. (ex. 3000.1)
#. Create jenkins jobs that test the new release branch.
#. Run through a manual test run based off of the head of the branch.
#. Generate the new man pages for the release.
#. Create internal tag for testing.(ex v3000.1)
#. Build all release packages.
#. Run manual and package tests against new packages.
#. Update installation instructions with new release number at `repo.saltproject.io`_.
#. Update and build docs to include new version. (ex. 3000.1)
#. Pre-announce on salt-users google groups that we are about to update our repo.
#. Push the internal tag live to salt's repo.
#. Publish release archive to pypi based off tag.
#. Push the packages live.
#. Publish release (v3000) archive to pypi based off tag.
#. Publish all packages live to repo.
#. Publish the docs.
#. Create release at `github`_
#. Update win-repo-ng with new salt versions.
#. Announce release is live to irc, salt-users, salt-announce and release slack channel.

.. _`github`: https://github.com/saltstack/salt/releases
.. _`repo.saltproject.io`: https://repo.saltproject.io
