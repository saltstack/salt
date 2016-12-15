.. _labels-and-milestones:

============================
GitHub Labels and Milestones
============================

SaltStack uses several label categories, as well as milestones, to triage incoming issues and pull requests in the
GitHub issue tracker.  Labels are used to sort issues by type, priority, severity, status, functional area, functional
group, and targeted release and pull requests by status, functional area, functional group, type of change, and test
status.  Milestones are used to indicate whether an issue is fully triaged or is scheduled to be fixed by SaltStack in
an upcoming sprint.

Milestones
==========

All issues are assigned to a milestone, whereas pull requests are almost never assigned to a milestone as the mean
lifetime of pull requests is short enough that there is no need to track them temporally.

SaltStack uses milestones to indicate which issues are blocked on submitter or upstream actions, are approved, or are
scheduled to be fixed or implemented in an upcoming sprint.  If an issue is not attached to a sprint milestone, you are
welcome to work on it at your own desire and convenience.  If it is attached to a sprint milestone and you have already
begun working on it or have a solution in mind or have other ideas related to the issue, you are encouraged to
coordinate with the assignee via the GitHub issue tracker to create the best possible solution or implementation.

``Approved``
    The issue has been validated and has all necessary information.

``Blocked``
    The issue is waiting on actions by parties outside of SaltStack, such as receiving more information from the
    submitter or resolution of an upstream issue.  This milestone is usually applied in conjunction with the labels
    ``Info Needed``, ``Question``, ``Expected Behavior``, ``Won't Fix For Now``, or ``Upstream Bug``.

``Under Review``
    The issue is having further validation done by a SaltStack engineer.

``<Sprint>``
    The issue is being actively worked on by a SaltStack engineer.  Sprint milestones names are constructed from the
    chemical symbol of the next release's codename and the number of sprints until that release is made.  For example,
    if the next release codename is ``Neon`` and there are five sprints until that release, the corresponding sprint
    milestone will be called ``Ne 5``.  See :ref:`<version-numbers>` for a discussion of Salt's release
    codenames.

Labels
======

Labels are used to sort and describe issues and pull requests.  Some labels are usually reserved for one or the other,
though most labels may be applied to both.

New issues will receive at least one label and a milestone, and new pull requests will receive at least one label.
Except for the :ref:`functional area <functional-area-labels>` and :ref:`functional group <functional-group-labels>`
label categories, issues will generally receive only up to one label per category.

Type
----

Issues are categorized into one of several types.  Type labels are almost never used for pull requests.  GitHub treats
pull requests like issues in many ways, so a pull request could be considered an issue with an implicit ``Pull Request``
type label applied.

``Feature``
    The issue is a request for new functionality including changes, enhancements, refactors, etc.

``Bug``
    The issue documents broken, incorrect, or confusing behavior.  This label is always accompanied by a :ref:`severity
    label <bug-severity-labels>`.

``Duplicate``
    The issue is a duplicate of another feature request or bug report.

``Upstream Bug``
    The issue is a result of an upstream issue.

``Question``
    The issue is more of a question than a request for new features or a report of broken features, but can sometimes
    lead to further discussion or changes of confusing or incongruous behavior or documentation.

``Expected Behavior``
    The issue is a bug report of intended functionality.

Priority
--------

An issue's priority is relative to its :ref:`functional area <functional-area-labels>`.  If a bug report, for example,
about ``gitfs`` indicates that all users of ``gitfs`` will encounter this bug, then a ``P1`` label will be applied, even
though users who are not using ``gitfs`` will not encounter the bug.  If a feature is requested by many users, it may be
given a high priority.

``P1``
    The issue will be seen by all users.

``P2``
    The issue will be seen by most users.

``P3``
    The issue will be seen by about half of users.

``P4``
    The issue will not be seen by most users.  Usually the issue is a very specific use case or corner case.

.. _bug-severity-labels:

Severity
--------

Severity labels are almost always only applied to issues labeled ``Bug``.

``Blocker``
    The issue is blocking an impending release.

``Critical``
    The issue causes data loss, crashes or hangs salt processes, makes the system unresponsive, etc.

``High Severity``
    The issue reports incorrect functionality, bad functionality, a confusing user experience, etc.

``Medium Severity``
    The issue reports cosmetic items, formatting, spelling, colors, etc.

.. _functional-area-labels:

Functional Area
---------------

Many major components of Salt have corresponding GitHub labels.  These labels are applied to all issues and pull
requests as is reasonably appropriate.  They are useful in organizing issues and pull requests according to the source
code relevant to issues or the source code changed by pull requests.

* ``Execution Module``
* ``File Servers``
* ``Grains``
* ``Multi-Master``
* ``Packaging``  Related to packaging of Salt, not Salt's support for package management.
* ``Pillar``
* ``RAET``
* ``Returners``
* ``Runners``
* ``SPM``
* ``Salt-API``
* ``Salt-Cloud``
* ``Salt-SSH``
* ``Salt-Syndic``
* ``State Module``
* ``Tests``
* ``Transport``
* ``Windows``
* ``ZMQ``

.. _functional-group-labels:

Functional Group
----------------

These labels sort issues and pull requests according to the internal SaltStack engineering teams.

``Core``
    The issue or pull request relates to code that is central or existential to Salt itself.

``Platform``
    The issue or pull request relates to support and integration with various platforms like traditional operating
    systems as well as containers, platform-based utilities like filesystems, command schedulers, etc., and
    system-based applications like webservers, databases, etc.

``RIoT``
    The issue or pull request relates to support and integration with various abstract systems like cloud providers,
    hypervisors, API-based services, etc.

``Console``
    The issue or pull request relates to the SaltStack enterprise console.

``Documentation``
    The issue or pull request relates to documentation.

Status
------

Status labels are used to define and track the state of issues and pull requests.  Not all potential statuses correspond
to a label, but some statuses are common enough that labels have been created for them.  If an issue has not been moved
beyond the ``Blocked`` milestone, it is very likely that it will only have a status label.

``Bugfix - back-port``
    The pull request needs to be back-ported to an older release branch.  This is done by :ref:`recreating the pull
    request <backporting-pull-requests>` against that branch.  Once the back-port is completed, this label is replaced
    with a ``Bugfix - [Done] back-ported`` label.  Normally, new features should go into the develop and bug fixes into
    the oldest supported release branch, see :ref:`<which-salt-branch>`.

``Bugfix - [Done] back-ported``
    The pull request has been back-ported to an older branch.

``Cannot Reproduce``
    The issue is a bug and has been reviewed by a SaltStack engineer, but it cannot be replicated with the provided
    information and context.  Those involved with the bug will need to work through additional ideas until the bug can
    be isolated and verified.

``Confirmed``
    The issue is a bug and has been confirmed by a SaltStack engineer, who often documents a minimal working example
    that reproduces the bug.

``Fixed Pending Verification``
    The issue is a bug and has been fixed by one or more pull requests, which should link to the issue.  Closure of the
    issue is contingent upon confirmation of resolution from the submitter.  If the submitter reports a negative
    confirmation, this label is removed.  If no response is given after a few weeks, then the issue will be assumed
    fixed and closed.

``Info Needed``
    The issue needs more information before it can be verified and resolved.  For a feature request this may include a
    description of the use cases.  Almost all bug reports need to include at least the versions of salt and its
    dependencies, the system type and version, commands used, debug logs, error messages, and relevant configs.

``Pending Changes``
    The pull request needs additional changes before it can be merged.

``Pending Discussion``
    The issue or pull request needs more discussion before it can be closed or merged.  The status of the issue or pull
    request is not clear or apparent enough for definite action to be taken, or additional input from SaltStack, the
    submitter, or another party has been requested.

    If the issue is not a pull request, once the discussion has arrived at a cogent conclusion, this label will be
    removed and the issue will be accepted.  If it is a pull request, the results of the discussion may require
    additional changes and thus, a ``Pending Changes`` label.

``Won't Fix for Now``
    The issue is legitimate, but it is not something the SaltStack team is currently able or willing to fix or
    implement.  Issues having this label may be revisited in the future.

Type of Change
~~~~~~~~~~~~~~

Every pull request should receive a change label.  These labels measure the quantity of change as well as the
significance of the change.  The amount of change and the importance of the code area changed are considered, but often
the depth of secondary code review required and the potential repercussions of the change may also advise the label
choice.

Core code areas include: state compiler, crypto engine, master and minion and syndic daemons, transport, pillar
rendering, loader, transport layer, event system, salt.utils, client, cli, logging, netapi, runner engine, templating
engine, top file compilation, file client, file server, mine, salt-ssh, test runner, etc.

Non-core code usually constitutes the specific set of plugins for each of the several plugin layers of Salt: execution
modules, states, runners, returners, clouds, etc.

``Minor Change``
    * Less than 64 lines changed, or
    * Less than 8 core lines changed
``Medium Change``
    * Less than 256 lines changed, or
    * Less than 64 core lines changed
``Master Change``
    * More than 256 lines changed, or
    * More than 64 core lines changed
``Expert Change``
    * Needs specialized, in-depth review

Test Status
-----------

These labels relate to the status of the automated tests that run on pull requests.  If the tests on a pull request fail
and are not overridden by one of these labels, the pull request submitter needs to update the code and/or tests so that
the tests pass and the pull request can be merged.

``Lint``
    The pull request has passed all tests except for the code lint checker.

``Tests Passed``
    The pull request has passed all tests even though some test results are negative.  Sometimes the automated testing
    infrastructure will encounter internal errors unrelated to the code change in the pull request that cause test runs
    to fail.  These errors can be caused by cloud host and network issues and also Jenkins issues like erroneously
    accumulating workspace artifacts, resource exhaustion, and bugs that arise from long running Jenkins processes.

Other
-----

These labels indicate miscellaneous issue types or statuses that are common or important enough to be tracked and sorted
with labels.

``Awesome``
    The pull request implements an especially well crafted solution, or a very difficult but necessary change.

``Help Wanted``
    The issue appears to have a simple solution.  Issues having this label
    should be a good starting place for new contributors to Salt.

``Needs Testcase``
    The issue or pull request relates to a feature that needs test coverage.  The pull request containing the tests
    should reference the issue or pull request having this label, whereupon the label should be removed.

``Regression``
    The issue is a bug that breaks functionality known to work in previous releases.

``Story``
    The issue is used by a SaltStack engineer to track progress on multiple related issues in a single place.

``Stretch``
    The issue is an optional goal for the current sprint but may not be delivered.

``ZD``
    The issue is related to a Zendesk customer support ticket.

``<Release>``
    The issue is scheduled to be implemented by ``<Release>``.  See :ref:`<version-numbers>` for a
    discussion of Salt's release codenames.
