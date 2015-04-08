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

All new SaltStack code is posted to the `develop` branch, which is the single
point of entry. The only exception is when a bugfix to develop cannot be
cleanly merged into a release branch and the bugfix needs to be rewritten for
the release branch.

Release Branching
=================

SaltStack maintains two types of releases, `Feature Releases` and
`Point Releases`. A feature release is managed by incrementing the first or
second release point number, so 0.10.5 -> 0.11.0 signifies a feature release
and 0.11.0 -> 0.11.1 signifies a point release, also a hypothetical
0.42.7 -> 1.0.0 would also signify a feature release.

Feature Release Branching
-------------------------

Each feature release is maintained in a dedicated git branch derived from the
last applicable release commit on develop. All file changes relevant to the
feature release will be completed in the develop branch prior to the creation
of the feature release branch. The feature release branch will be named after
the relevant numbers to the feature release, which constitute the first two
numbers. This means that the release branch for the 0.11.0 series is named
0.11.

A feature release branch is created with the following command:

.. code-block:: bash

    # git checkout -b 0.11 # From the develop branch
    # git push origin 0.11

Point Releases
--------------

Each point release is derived from its parent release branch. Constructing point
releases is a critical aspect of Salt development and is managed by members of
the core development team. Point releases comprise bug and security fixes which
are cherry picked from develop onto the aforementioned release branch. At the
time when a core developer accepts a pull request a determination needs to be
made if the commits in the pull request need to be backported to the release
branch. Some simple criteria are used to make this determination:

* Is this commit fixing a bug?
  Backport
* Does this commit change or add new features in any way?
  Don't backport
* Is this a PEP8 or code cleanup commit?
  Don't backport
* Does this commit fix a security issue?
  Backport

Determining when a point release is going to be made is up to the project
leader (Thomas Hatch). Generally point releases are made every 1-2 weeks or
if there is a security fix they can be made sooner.

The point release is only designated by tagging the commit on the release
branch with release number using the existing convention (version 0.11.1 is
tagged with v0.11.1). From the tag point a new source tarball is generated
and published to PyPI, and a release announcement is made.