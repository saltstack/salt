.. _labels-and-milestones:

============================
GitHub Labels and Milestones
============================

SaltStack uses several labeling schemes, as well as applying milestones, to triage incoming issues and pull requests in
the GitHub Issue Tracker. Most of the labels and milestones are used for internal tracking, but the following
definitions might prove useful for the community to discover the best issues to help resolve.

Milestones
==========

Milestones are most often applied to issues, as a milestone is assigned to every issue that has been triaged. However,
milestones can also be applied to pull requests. SaltStack uses milestones to track bugs or features that should be
included in the next major feature release, or even the next bug-fix release, as well as what issues are ready to be
worked on or what might be blocked. All incoming issues must have a milestone associated with them.

Approved
    Used to indicate that this issue has all of the needed information and is ready to be worked on.

Blocked
    Used to indicate that the issue is not ready to be worked on yet. This typically applies to issues that have been
    labeled with “Info Needed”, “Question”, “Expected Behavior”, “Won’t Fix for Now”, etc.

Dot or Bug-fix Release
    Used to help filter/identify what issues must be fixed before the release such as 2014.7.4 or 2015.2.3. This
    milestone is often used in conjunction with the ``Blocker`` label, but not always.

Feature Release
    Similar to the Dot or Bug-fix Release milestone, but for upcoming feature releases such as Boron, Carbon, etc.
    This milestone is often used in conjunction with the ``Blocker`` label, but not always.

Labels
======

Labels are used to facilitate the resolution of new pull requests and open issues. Most labels are confined to being
applied to either issues or pull requests, though some labels may be applied to both.

Issue Labels
------------

All incoming issues should be triaged with at least one label and a milestone. When a new issue comes in, it should be
determined if the issue is a bug or a feature request, and either of those labels should be applied accordingly. Bugs
and Feature Requests have differing labeling schemes, detailed below, where other labels are applied to them to further
help contributors find issues to fix or implement.

There are some labels, such as ``Question`` or some of the "Status" labels that may be applied as "stand alone" labels
in which more information may be needed or a decision must be reached on how to proceed. (See the "Bug Status Labels"
section below.)

Feature Requests
~~~~~~~~~~~~~~~~

The ``Feature Request`` label should be applied when a user is requesting entirely new functionality. This can include
new functions, modules, states, modular systems, flags for existing functions, etc. Features *do not* receive severity
or priority labels, as those labels are only used for bugs. However, they may receive "Functional Area" labels or "ZD".

Feature request issues will be prioritized on an "as-needed" basis using milestones during SaltStack's feature release
and sprint planning processes.

Bugs
~~~~

All bugs should have the ``Bug`` label as well as a severity, priority, functional area, and a status, as applicable.

Severity
^^^^^^^^

How severe is the bug? SaltStack uses four labels to determine the severity of a bug: ``Blocker``, ``Critical``,
``High``, and ``Medium``. This scale is intended to make the bug-triage process as objective as possible.

Blocker
    Should be used sparingly to indicate must-have fixes for the impending release.

Critical
    Applied to bugs that have data loss, crashes, hanging, unresponsive system, or have no workaround.

High Severity
    Any bug report that contains incorrect functionality, bad functionality, a confusing user experience, or has a
    possible workaround.

Medium Severity
    Applied to bugs that are about cosmetic items, spelling, spacing, colors, etc.

Priority
^^^^^^^^

In addition to using a bug severity to classify issues, a priority is also assigned to each bug to give further
granularity in searching for bugs to fix. In this way, a bug's priority is defined as follows:

P1
    Very likely. Everyone will see the bug.

P2
    Somewhat likely. Most will see the bug, but a few will not.

P3
    Half will see the bug, about half will not.

P4
    Most will not see the bug. Usually a very specific use case or corner case.

.. note::

    A bug's priority is relative to its functional area. If a bug report, for example, about ``gitfs`` includes details
    indicating that everyone who ``gitfs`` will run into this bug, then a ``P1`` label will be applied, even though
    Salt users who are not enabling ``gitfs`` will see the bug.

Functional Areas
^^^^^^^^^^^^^^^^

All bugs should receive a "Functional Area" label to indicate what region of Salt the bug is mainly seen in. This will
help internal developers as well as community members identify areas of expertise to find issues that can be fixed more
easily. Functional Area labels can also be applied to Feature Requests.

Functional Area Labels, in alphabetical order, include:

* Core
* Documentation
* Execution Module
* File Servers
* Multi-Master
* Packaging
* Pillar
* Platform Mgmt.
* RAET
* Returners
* Salt-API
* Salt-Cloud
* Salt-SSH
* Salt-Syndic
* State Module
* Windows
* ZMQ

Bug Status Labels
^^^^^^^^^^^^^^^^^

Status lables are used to define and track the state a bug is in at any given time. Not all bugs will have a status
label, but if a SaltStack employee is able to apply a status label, he or she will. Status labels are somewhat unique
in the fact that they might be the only label on an issue, such as ``Pending Discussion``, ``Info Needed``, or
``Expected Behavior`` until further action can be taken.

Cannot Reproduce
    Someone from the SaltStack team has tried to reproduce the bug with the given information but they are unable to
    replicate the problem. More information will need to be provided from the original issue-filer before proceeding.

Confirmed
    A SaltStack engineer has confirmed the reported bug and provided a simple way to reproduce the failure.

Duplicate
    The issue has been reported already in another report. A link to the other bug report must be provided. At that
    point the new issue can be closed. Usually, the earliest bug on file is kept as that typically has the most
    discussion revolving around the issue, though not always. (This can be a "stand-alone" label.)

Expected Behavior
    The issue reported is expected behavior and nothing needs to be fixed. (This can be a "stand-alone" label.)

Fixed Pending Verification
    The bug has been fixed and a link to the applicable pull request(s) has been provided, but confirmation is being
    sought from the community member(s) involved in the bug to test and confirm the fix.

Info Needed
    More information about the issue is needed before proceeding such as a versions report, a sample state, the command
    the user was running, or the operating system the error was occurring on, etc. (This can be a "stand-alone" label.)

Upstream Bug
    The reported bug is something that cannot be fixed in the Salt code base but is instead a bug in another library
    such a bug in ZMQ or Python. When an issue is labeled with ``Upstream Bug`` then a bug report in the upstream
    project must be filed (or found if a report already exists) and a link to the report must be provided to the issue
    in Salt for tracking purposes. (This can be a stand-alone label.)

Won't Fix for Now
    The SaltStack team has acknowledged the issue at hand is legitimate, but made the call that it’s not something
    they’re able or willing to fix at this time. These issues may be revisited in the future.

Other
~~~~~

There are a couple of other labels that are helpful in categorizing bugs that are not included in the categories above.
These labels can either stand on their own such as ``Question`` or can be applied to bugs or feature requests as
applicable.

Low Hanging Fruit
    Applied to bugs that should be easy to fix. This is useful for new contributors to know where some simple things
    are to get involved in contributing to salt.

Question
    Used when the issue isn’t a bug nor a feature, but the user has a question about expected behavior, how something
    works, is misunderstanding a concept, etc. This label is typically applied on its own with ``Blocked`` milestone.

Regression
    Helps with additional filtering for bug fixing. If something previously worked and now does not work, as opposed to
    something that never worked in the first place, the issue should be treated with greater urgency.

ZD
    Stands for “Zen Desk” and is used to help track bugs that customers are seeing as well. Bugs with this label should
    be treated with greater urgency.

Pull Request Labels
-------------------


Labels that Bridge Issues and Pull Requests
===========================================

Needs Testcase
    Used by SaltStack's QA team to realize where pain points are and to bring special attention to where some test
    coverage needs to occur, especially in areas that have regressed. This label can apply to issues or pull requests,
    which can also be open or closed. Once tests are written, the pull request containing the tests should be linked to
    the issue or pull request that originally had the ``Needs Testcase`` label. At this point, the ``Needs Testcase``
    label must be removed to indicate that tests no longer need to be written.

Pending Discussion
    If this label is applied to an issue, the issue may or may not be a bug. Enough information was provided about the
    issue, but some other opinions on the issue are desirable before proceeding. (This can be a "stand-alone" label.)
    If the label is applied to a pull request, this is used to signal that further discussion must occur before a
    decision is made to either merge the pull request into the code base or to close it all together.
