====================
Salt Release Process
====================

The goal for Salt projects is to cut a new feature release every four to six
weeks.  This document outlines the process for these releases, and the
subsequent bug fix releases which follow.


Feature Release Process
=======================

When a new release is ready to be cut, the person responsible for cutting the
release will follow the following steps (written using the 0.16 release as an
example):

#. All open issues on the release milestone should be moved to the next release
   milestone. (e.g. from the ``0.16`` milestone to the ``0.17`` milestone)
#. Release notes should be created documenting the major new features and
   bugfixes in the release.
#. Create an annotated tag with only the major and minor version numbers,
   preceded by the letter ``v``.  (e.g. ``v0.16``)  This tag will reside on the
   ``develop`` branch.
#. Create a branch for the new release, using only the major and minor version
   numbers.  (e.g. ``0.16``)
#. On this new branch, create an annotated tag for the first revision release,
   which is generally a release candidate.  It should be preceded by the letter
   ``v``.  (e.g. ``v0.16.0RC``)
#. The release should be packaged from this annotated tag and uploaded to PyPI.
#. The packagers should be notified on the ``salt-packagers`` mailing list so
   they can create packages for all the major operating systems.  (note that
   release candidates should go in the testing repositories)
#. After the packagers have been given a few days to compile the packages, the
   release is announced on the ``salt-users`` mailing list.
#. Log into RTD and add the new release there.  (Have to do it manually)


Maintenance and Bugfix Releases
===============================

Once a release has been cut, regular cherry-picking sessions should begin to
cherry-pick any bugfixes from the ``develop`` branch to the release branch
(e.g. ``0.16``).  Once major bugs have been fixes and cherry-picked, a bugfix
release can be cut:

#. On the release branch (i.e. ``0.16``), create an annotated tag for the
   revision release.  It should be preceded by the letter ``v``.  (e.g.
   ``v0.16.1``)  Release candidates are unnecessary for bugfix releases.
#. The release should be packaged from this annotated tag and uploaded to PyPI.
#. The packagers should be notified on the ``salt-packagers`` mailing list so
   they can create packages for all the major operating systems.
#. After the packagers have been given a few days to compile the packages, the
   release is announced on the ``salt-users`` mailing list.
