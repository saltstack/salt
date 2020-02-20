.. _labels-and-milestones:

============================
GitHub Labels and Milestones
============================

SaltStack uses several label categories, as well as milestones, to triage
incoming issues and pull requests in the GitHub issue tracker.  Labels are used
to sort issues by type, severity, status, and targeted release if applicable.
Pull requests might use labels, but will not necessarily always include a label.
Milestones are used to indicate whether an issue is fully triaged.

.. _milestone-labels:

Milestones
==========

All issues are assigned to a milestone, whereas pull requests are almost never
assigned to a milestone as the mean lifetime of pull requests is short enough
that there is no need to track them temporally.

SaltStack uses milestones to indicate which issues are blocked on submitter or
upstream actions, are approved.

- ``Approved`` - The issue has been validated and has all necessary information.

- ``Blocked`` - The issue is waiting on actions by parties outside of
  SaltStack, such as receiving more information from the submitter or
  resolution of an upstream issue. This milestone is usually applied in
  conjunction with the labels ``Info Needed``, ``Question``,
  ``Expected Behavior``, ``Won't Fix For Now``, or ``Upstream Bug``.

Issue Labels
============

Labels are used to sort and describe issues. New issues will receive at least
one label and a milestone.

.. _info-labels:

Information and Discussion
--------------------------

If an issue does not have adequate information or requires discussion from
other individuals outside of the user reporting the issue one of the following
labels will need to be applied:

- ``Info Needed`` - The issue needs more information before it can be verified
  and resolved.  For a feature request this may include a description of the
  use cases.  Almost all bug reports need to include at least the versions of
  salt and its dependencies, the system type and version, commands used, debug
  logs, error messages, and relevant configs.

- ``Pending Discussion`` - The issue needs more discussion before it can be further
  triaged.  The status of the issue is not clear or apparent enough
  for definite action to be taken, and requires additional input from another SaltStack
  member, a community member, or another party has been requested.
  Once the discussion has arrived at a cogent conclusion, this label will be
  removed and the issue will either be accepted or closed dependent on the
  outcome of the discussion.

.. _type-labels:

Type
----

Issues are categorized into one of several types.

- ``Feature`` - The issue is a request for new functionality including changes,
  enhancements, refactors, etc. If the feature request is substantial and requires
  to be put through a design process, the triage user will need to close the issue
  and request the original author submit a
  `Salt Enhancement Proposal <https://github.com/saltstack/salt-enhancement-proposals>`_

- ``Documentation`` - The issue is related to improving only the documentation.

- ``Bug`` - The issue documents broken, incorrect, or confusing behavior.  This
  label is always accompanied by a :ref:`severity label <bug-severity-labels>`.

- ``Duplicate`` - The issue is a duplicate of another feature request or bug
  report. If a duplicate, the issue will be closed in favor of the other issue

- ``Upstream Bug`` - The issue is a result of an upstream issue. The issue will
  stay open in order to help track

- ``Question`` - The issue is more of a question than a request for new
  features or a report of broken features, but can sometimes lead to further
  discussion or changes of confusing or incongruous behavior or documentation.
  If the question is answered and there is no further discussion required the
  issue will be closed.

- ``Expected Behavior`` - The issue is a bug report of intended functionality. If
  determined to be exepected behavior the issue will be closed.

.. _bug-severity-labels:

Severity
--------

- ``Critical`` - These are issues that cause data loss, prevent Salt
  from starting, cause Salt to crash, etc.

- ``High`` - The issue affects the system severly
  with no workaround but other parts remain functional.

- ``Medium`` - The issue reports incorrect functionality, bad
  functionality, a confusing user experience, etc.

- ``Low`` - The issue reports cosmetic items, formatting, spelling,
  colors, etc.

.. _status-labels:

Status
------

Status labels are used to define and track the state of issues. Not all potential
statuses correspond to a label, but some statuses are common enough that labels
have been created for them.  If an issue has not been moved beyond the ``Blocked``
milestone, it is very likely that it will only have a status label.

- ``Cannot Reproduce`` - The issue is a bug and has been reviewed by a
  SaltStack engineer, but it cannot be replicated with the provided information
  and context.  Those involved with the bug will need to work through
  additional ideas until the bug can be isolated and verified.

- ``Confirmed`` - The issue is a bug and has been confirmed by a SaltStack
  engineer, who often documents a minimal working example that reproduces the
  bug.

- ``Fixed Pending Verification`` - The issue is a bug and has been fixed by one
  or more pull requests, which should link to the issue.  Closure of the issue
  is contingent upon confirmation of resolution from the submitter.  If the
  submitter reports a negative confirmation, this label is removed.  If no
  response is given after a few weeks, then the issue will be assumed fixed and
  closed.

- ``Won't Fix for Now`` - The issue is legitimate, but it is not something the
  SaltStack team is currently able or willing to fix or implement.  Issues
  having this label may be revisited in the future.

Pull Request Labels
===================
Not all pull requests will have a label applied, but sometimes the following will
be applied in certain sitations:

- ``Needs Testcase`` - The pull request cannot be merged until test coverage for the
  bug or feature has been added.

- ``Merge Ready`` - The PR has all required reviews, the tests are passing and its ready
  to be merged. The team in charge of merging PRs will prioritize merging these PRs that
  are ready.

Other Pull Request and Issue Labels
===================================

These labels indicate miscellaneous issue types or statuses that are common or
important enough to be tracked and sorted with labels.

- ``Awesome`` - The pull request implements an especially well crafted
  solution, or a very difficult but necessary change.

- ``Help Wanted`` - The issue appears to have a simple solution.  Issues having
  this label should be a good starting place for new contributors to Salt.

- ``Regression`` - The issue is a bug that breaks functionality known to work
  in previous releases.

- ``ZD`` - The issue is related to a Zendesk customer support ticket.

- ``<Release>`` - The issue is scheduled to be implemented by ``<Release>``.
  See :ref:`here <version-numbers>` for a discussion of Salt's release
  codenames.
