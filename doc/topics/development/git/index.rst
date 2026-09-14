.. _saltstack-git-policy:

====================
SaltStack Git Policy
====================

This page documents the branching model the Salt maintainers use day to day.
Contributors do not need to memorize it - the short version is in
:ref:`contributing-branch-choice`. Read on if you are doing release work,
porting a patch yourself, or want to understand why the maintainers
restructured your PR.

Branch layout
=============

Salt uses a long-lived ``master`` branch plus one branch per maintained
feature release. The current set:

- ``3006.x`` - Sulfur (LTS).
- ``3007.x`` - Chlorine.
- ``3008.x`` - Argon.
- ``master`` - Potassium, the in-development next release.

Each release branch carries the bug fixes for that release line and nothing
else. New features only land on ``master``.

When a feature release is cut, a new branch is created from ``master`` at the
release commit and named ``<major>.x`` (for example, ``3008.x``). ``master``
then moves on to the next release name. Branches for releases that have
reached end of life are kept read-only for history.

Merge-forward
=============

Bug fixes are merged forward: a PR opened against ``3006.x`` is merged there,
then merged forward into ``3007.x``, ``3008.x``, and ``master`` by the
maintainers. Contributors do not need to open four PRs.

This is why we ask you to open against the **oldest** branch the fix applies
to. Opening against ``master`` for a bug that also exists in ``3006.x`` means
either the fix never reaches users on 3006.x, or someone has to redo the work
as a backport.

Where conflicts make a clean merge-forward impossible, the maintainer
performing the merge-forward will open a follow-up PR resolving the
conflict, attributed to the original author.

Hotfix and patch releases
=========================

Point releases (for example, 3006.13) are tagged off the corresponding
release branch and contain only changes already merged into that branch.
There is no separate hotfix workflow - merging the fix into the release
branch is the hotfix.

Larger process changes - the release cadence itself, new branch policies,
deprecation policy - go through the Salt Enhancement Proposal process. See
the `salt-enhancement-proposals
<https://github.com/saltstack/salt-enhancement-proposals>`__ repository for
the active proposals and the template.
