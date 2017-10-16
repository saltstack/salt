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

All new SaltStack code should be submitted against either the ``develop`` branch
or a point release branch, depending on the nature of the submission. Please see
the :ref:`Which Salt Branch? <which-salt-branch>` section of Salt's
:ref:`Contributing <contributing>` documentation or the Release Branching section
section below for more information.

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
feature release will be completed in the develop branch prior to the creation
of the feature release branch. The feature release branch will be named after
the relevant numbers to the feature release, which constitute the first two
numbers. This means that the release branch for the 2015.8.0 series is named
2015.8.

A feature release branch is created with the following command:

.. code-block:: bash

    # git checkout -b 2015.8 # From the develop branch
    # git push origin 2015.8

Point Releases
--------------

Each point release is derived from its parent release branch. Constructing point
releases is a critical aspect of Salt development and is managed by members of
the core development team. Point releases comprise bug and security fixes. Bug
fixes can be made against a point release branch in one of two ways: the bug
fix can be submitted directly against the point release branch, or an attempt
can be made to back-port the fix to the point release branch.

Bug fixes should be made against the earliest supported release branch on which
the bug is present. The Salt development team regularly merges older point
release branches forward into newer point release branches. That way, the bug
fixes that are submitted to older release branches can cascade up through all
related release branches.

For more information, please see the :ref:`Which Salt Branch? <which-salt-branch>`
section of Salt's :ref:`Contributing <contributing>` documentation.

Determining when a point release is going to be made is up to the project
leader (Thomas Hatch). Generally point releases are made every 2-4 weeks or
if there is a security fix they can be made sooner.

The point release is only designated by tagging the commit on the release
branch with a release number using the existing convention (version 2015.8.1
is tagged with v2015.8.1). From the tag point a new source tarball is generated
and published to PyPI, and a release announcement is made.