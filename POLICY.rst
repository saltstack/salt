=================================
Salt Project maintenance policies
=================================

This document explains the current project maintenance policies. The goal of
these policies are to reduce the maintenance burden on core maintainers of the
Salt Project and to encourage more active engagement from the Salt community.

* `Issue management`_
* `Pull request management`_
* `Salt Enhancement Proposals (SEP) process`_


Issue management
================
Issues for the Salt Project are critical to Salt community communication and to
find and resolve issues in the Salt Project. As such, the issue tracker needs to
be kept clean and current to the currently supported releases of Salt. They also
need to be free of feature requests, arguments, and trolling.

We have decided to update our issue policy to be similar to RedHat community
project policies.

Community members who repeatedly violate these policies are subject to bans.

#. All issues that were not opened against a currently supported release of Salt
   will be closed.

   - When an old release of Salt is marked out of support, all issues opened
     against the now defunct release will be closed.
   - If the issue is still present in the current release of Salt, submit a new
     issue. Do not re-open the old issue after it has been closed.
   - When opening a new issue that was a bug in a previous release of Salt, you
     must validate it against a currently supported release of Salt for
     consideration. Issues that do not show the problem against a current
     release will be closed without consideration.

#. Only defects can be submitted to the issue tracker.

   - Feature requests without a PR will be immediately closed.
   - Feature requests must be designated as a feature being developed and owned
     by the issue submitter and assigned to a release. Otherwise they will be
     immediately closed.
   - Discussions about features can be held in the GitHub
     `Discussions <https://github.com/saltstack/salt/discussions>`_ tab or in
     the community `Open Hour <https://saltproject.io/calendar/>`_.
   - Questions will be immediately closed.

#. Issues must submit sufficient information.

   - Issues must follow the relevant template for information.
   - Issues that do not give sufficient information about the nature of the
     issue **and how to reproduce the issue** will be immediately closed.
   - Issues that do not comply will be immediately closed.


Pull request management
=======================
The Salt pull request (PR) queue has been a challenge to maintain for the entire
life of the project. This is in large part due to the incredibly active and
vibrant community around Salt.

Unfortunately, it has proven to be too much for the core team and the greater
Salt community to manage. As such, we deem it necessary to make fundamental
changes to how we manage the PR queue:

#. All PRs opened against releases of Salt that are no longer supported will be
   closed immediately.
#. Closed PRs can be resubmitted, NOT re-opened.
#. PRs need to provide full tests for all of the code affected, regardless of
   whether the PR author wrote the code affected.
#. PR tests need to be written using the current test mechanism (pytest).
#. PRs need to pass tests.
#. PRs must NOT increase the overall test time by a noticeable length.
#. PRs must NOT add new plugins directly to Salt unless sanctioned by the Salt
   core team. New plugins should be made into Salt Extensions.
#. PRs that have not been updated due to inactivity will be closed. Inactivity
   is determined by a lack of submitter activity for the space of 1 month.
#. PR tests should always maintain or increase total code coverage.


Salt Enhancement Proposals (SEP) process
========================================
**A message from Thomas Hatch, creator of Salt:**

In 2019, we decided to create a community process to discuss and review Salt
Enhancement Proposals (SEPs). Unfortunately, I feel that this process has not
proven to be an effective way to solve the core issues around Salt Enhancements.
Overall, the Salt enhancement process has proven itself to be more of a burden
than an accelerant to Salt stability, security, and progress. As such, I feel
that the current optimal course of action is to shut the process down.

Instead of the Salt Enhancement Proposal process, we will add a time in the
`Open Hour <https://saltproject.io/calendar/>`_ for people to present ideas and
concepts to better understand if they are worth their effort to develop.
Extensive documentation around more intrusive or involved enhancements should
be included in pull requests (PRs). Conversations about enhancements can also be
held in the `Discussions <https://github.com/saltstack/salt/discussions>`_ tab
in GitHub.

By migrating the conversation into the PR process, we ensure that we are only
reviewing viable proposals instead of being burdened with requests that the core
team is expected to fulfill.

Effective immediately (January 2024), we are archiving and freezing the SEP
repo.
