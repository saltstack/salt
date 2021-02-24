====================
SaltStack Git Policy
====================

The SaltStack team follows a git policy to maintain stability and consistency
with the repository.

The git policy has been developed to encourage contributions and make contributing
to Salt as easy as possible. Code contributors to SaltStack projects DO NOT NEED
TO READ THIS DOCUMENT, because all contributions come into SaltStack via a single
gateway to make it as easy as possible for contributors to give us code.

The primary rule of git management in SaltStack is to make life easy on
contributors and developers to send in code. Simplicity is always a goal!

New Code Entry
==============

All new SaltStack code should be submitted against ``master``.

Release Branching
=================

SaltStack maintains two types of releases, ``Feature Releases`` and
``Point Releases`` (also commonly referred to as ``Bugfix Releases``. A
feature release is managed by incrementing the first or second release point
number, so 2015.5.5 -> 2015.8.0 signifies a feature release
and 2015.8.0 -> 2015.8.1 signifies a point release.

Feature Release Branching
-------------------------

Each feature release is maintained in a dedicated git branch derived from the
last applicable release commit on develop. All file changes relevant to the
feature release will be completed in the ``master`` branch prior to the creation
of the feature release branch. The feature release branch will be named after
the relevant numbers to the feature release, which constitute the first two
numbers. This means that the release branch for the 2015.8.0 series is named
2015.8.

A feature release branch is created with the following command:

.. code-block:: bash

    # git checkout -b 2015.8 # From the master branch
    # git push origin 2015.8

Point Releases
--------------

As documented in `SEP 14 <https://github.com/saltstack/salt-enhancement-proposals/blob/master/accepted/0014-dev-overhaul.md#hotfix--patch-release>`__,
point releases should be rare.
