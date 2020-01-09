====================
Salt Release Process
====================

The goal for Salt projects is to cut a new feature release every six
months. This document outlines the process for these releases, and the
subsequent bug fix releases which follow.


Feature Release Process
=======================

When a new release is ready to be cut, the person responsible for cutting the
release will follow the following steps (written using the 2019.2.0 release as an
example):

#. Create first public draft of release notes with major features.
#. Remove any deprecations for the upcoming release.
#. Notify salt-users and salt-announce google groups when the feature freeze
   branch creation will occur so they can try to get their work merged.
#. Create QA test plan. Review features planned for the release and determine if
   there is sufficient test coverage.
#. Ensure all required features are merged.
#. Complete one last merge forward from the previous branch.
#. Create feature release branch with the name of the release. (ex. fluorine)
#. Create issue to start the process of deprecating for the next feature release.
#. Create jenkins jobs to test the new feature release branch.
#. Inform salt-users and salt-announce google groups feature branch and
   freeze is complete.
#. Add new feature branch to salt-jenkins repo and the kitchen yaml file.
#. Fix tests failing in jenkins test runs.
#. Finalize QA test plan and add all required tests.
#. Run through a manual test run based off of the head of the feature branch.
#. Convert the feature release branch to the version number. For example (v2019.2)
   This is based off of the year and month that is planned to release.
#. Migrate both the jenkins test jobs and salt-jenkins repo to the new branch number.
#. Notify salt-users and salt-announce google groups of the new version branch
   number and migrate any PRs to the new branch.
#. Delete old feature release branch name (ex. fluorine)
#. Update all name references to version number in the docs. For example
   all fluorine references in the docs needs to be moved to v2019.2.0
#. Create RC release branch. (ex. 2019.2.0.rc)
#. Create new jenkins test jobs with new RC release branch
#. Notify salt-users and salt-announce google groups of the new RC branch.
#. Fix tests failing in jenkins test runs.
#. Review the release notes with major features.
#. Generate the new man pages for the release.
#. Create internal RC tag for testing.
#. Build latest windows, mac, ubuntu, debian and redhat packages.
#. Run manual and package tests against new RC packages.
#. Update release candidate docs with the new version. (ex. 2019.2.0rc1)
#. Push the internal tag live to salt's repo.
#. Publish release archive to pypi based off tag.
#. Push the RC packages live.
#. Announce new RC to salt-users and salt-announce google groups.
#. Triage incoming issues based on the new RC release.
#. Fix RC issues once they are categorized as a release blocker.
#. Depending on the issues found during the RC process make a decesion
   on whether to release based off the RC or go through another RC process,
   repeating the steps starting at ensuring the tests are not failing.
#. If a RC is categorized as stable, build all required packages.
#. Test all release packages.
#. Test links from `repo.saltstack.com`_.
#. Update installation instructions with new release number at `repo.saltstack.com`_.
#. Update and build docs to include new version (2019.2) as the latest.
#. Pre-announce on salt-users google group that we are about to update our repo.
#. Publish release (v2019.2.0) archive to pypi based off tag.
#. Publish all packages live to repo.
#. Publish the docs.
#. Create release at `github`_
#. Update win-repo-ng with new salt versions.
#. Announce release is live to irc, salt-users, salt-announce and release slack
   community channel.


Maintenance and Bugfix Releases
===============================

Once a feature release branch has been cut from ``develop``, the branch moves
into a "feature freeze" state. The new release branch enters the ``merge-forward``
chain and only bugfixes should be applied against the new branch. Once major bugs
have been fixed, a bugfix release can be cut:

#. Ensure all required bug fixes are merged.
#. Inform salt-users and salt-announce we are going to branch for the release.
#. Complete one last merge forward from the previous branch.
#. Create release branch with the version of the release. (ex. 2019.2.1)
#. Create jenkins jobs that test the new release branch.
#. Fix tests failing in jeknins test runs.
#. Run through a manual test run based off of the head of the branch.
#. Generate the new man pages for the release.
#. Create internal tag for testing.(ex v2019.2.1)
#. Build all release packages.
#. Run manual and package tests against new packages.
#. Update installation instructions with new release number at `repo.saltstack.com`_.
#. Update and build docs to include new version. (ex. 2019.2.1)
#. Pre-announce on salt-users google groups that we are about to update our repo.
#. Push the internal tag live to salt's repo.
#. Publish release archive to pypi based off tag.
#. Push the packages live.
#. Publish release (v2019.2.1) archive to pypi based off tag.
#. Publish all packages live to repo.
#. Publish the docs.
#. Create release at `github`_
#. Update win-repo-ng with new salt versions.
#. Announce release is live to irc, salt-users, salt-announce and release slack channel.

For more information about the difference between the ``develop`` branch and
bugfix release branches, please refer to the :ref:`Which Salt Branch?
<which-salt-branch>` section of Salt's :ref:`Contributing <contributing>`
documentation.

.. _`github`: https://github.com/saltstack/salt/releases
.. _`repo.saltstack.com`: https://repo.saltstack.com
