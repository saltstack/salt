.. _contributing:

============
Contributing
============

There is a great need for contributions to Salt and patches are welcome! The goal
here is to make contributions clear, make sure there is a trail for where the code
has come from, and most importantly, to give credit where credit is due!

There are a number of ways to contribute to Salt development.

For details on how to contribute documentation improvements please review
:ref:`Writing Salt Documentation <salt-docs>`.


Salt Coding Style
-----------------

SaltStack has its own coding style guide that informs contributors on various coding
approaches. Please review the :ref:`Salt Coding Style <coding-style>` documentation
for information about Salt's particular coding patterns.

Within the :ref:`Salt Coding Style <coding-style>` documentation, there is a
section about running Salt's ``.testing.pylintrc`` file. SaltStack recommends
running the ``.testing.pylintrc`` file on any files you are changing with your
code contribution before submitting a pull request to Salt's repository. Please
see the :ref:`Linting<pylint-instructions>` documentation for more information.

.. note::

    There are two pylint files in the ``salt`` directory. One is the
    ``.pylintrc`` file and the other is the ``.testing.pylintrc`` file. The
    tests that run in Jenkins against GitHub Pull Requests use
    ``.testing.pylintrc``. The ``testing.pylintrc`` file is a little less
    strict than the ``.pylintrc`` and is used to make it easier for contributors
    to submit changes. The ``.pylintrc`` file can be used for linting, but the
    ``testing.pylintrc`` is the source of truth when submitting pull requests.


.. _github-pull-request:

Sending a GitHub pull request
-----------------------------

Sending pull requests on GitHub is the preferred method for receiving
contributions. The workflow advice below mirrors `GitHub's own guide <GitHub
Fork a Repo Guide_>`_ and is well worth reading.

#.  `Fork saltstack/salt`_ on GitHub.
#.  Make a local clone of your fork.

    .. code-block:: bash

         git clone git@github.com:my-account/salt.git
         cd salt

#.  Add `saltstack/salt`_ as a git remote.

    .. code-block:: bash

         git remote add upstream https://github.com/saltstack/salt.git

#.  Create a new branch in your clone.

    .. note::

        A branch should have one purpose. For example, "Fix bug X," or "Add
        feature Y".  Multiple unrelated fixes and/or features should be
        isolated into separate branches.

    If you're working on a bug or documentation fix, create your branch from
    the oldest **supported** main release branch that contains the bug or requires the documentation
    update. See :ref:`Which Salt Branch? <which-salt-branch>`.

    .. code-block:: bash

        git fetch upstream
        git checkout -b fix-broken-thing upstream/2016.11

    If you're working on a feature, create your branch from the |repo_primary_branch| branch.

    .. code-block:: bash

        git fetch upstream
        git checkout -b add-cool-feature upstream/|repo_primary_branch|

#.  Edit and commit changes to your branch.

    .. code-block:: bash

        vim path/to/file1 path/to/file2
        git diff
        git add path/to/file1 path/to/file2
        git commit

    Write a short, descriptive commit title and a longer commit message if
    necessary.

    .. note::

        If your change fixes a bug or implements a feature already filed in the
        `issue tracker`_, be sure to
	`reference the issue <https://help.github.com/en/articles/closing-issues-using-keywords>`_
        number in the commit message body.

    .. code-block:: bash

        Fix broken things in file1 and file2

        Fixes #31337

        # Please enter the commit message for your changes. Lines starting
        # with '#' will be ignored, and an empty message aborts the commit.
        # On branch fix-broken-thing
        # Changes to be committed:
        #       modified:   path/to/file1
        #       modified:   path/to/file2


    If you get stuck, there are many introductory Git resources on
    http://help.github.com.

#.  Push your locally-committed changes to your GitHub fork.

    .. code-block:: bash

        git push -u origin fix-broken-thing

    or

    .. code-block:: bash

        git push -u origin add-cool-feature

    .. note::

        You may want to rebase before pushing to work out any potential
        conflicts:

        .. code-block:: bash

            git fetch upstream
            git rebase upstream/2016.11 fix-broken-thing
            git push -u origin fix-broken-thing

        or

        .. code-block:: bash

            git fetch upstream
            git rebase upstream/|repo_primary_branch| add-cool-feature
            git push -u origin add-cool-feature

        If you do rebase, and the push is rejected with a
        ``(non-fast-forward)`` comment, then run ``git status``. You will
        likely see a message about the branches diverging:

        .. code-block:: text

            On branch fix-broken-thing
            Your branch and 'origin/fix-broken-thing' have diverged,
            and have 1 and 2 different commits each, respectively.
              (use "git pull" to merge the remote branch into yours)
            nothing to commit, working tree clean

        Do **NOT** perform a ``git pull`` or ``git merge`` here. Instead, add
        ``--force-with-lease`` to the end of the ``git push`` command to get the changes
        pushed to your fork. Pulling or merging, while they will resolve the
        non-fast-forward issue, will likely add extra commits to the pull
        request which were not part of your changes.

#.  Find the branch on your GitHub salt fork.

    https://github.com/my-account/salt/branches/fix-broken-thing

#.  Open a new pull request.

    Click on ``Pull Request`` on the right near the top of the page,

    https://github.com/my-account/salt/pull/new/fix-broken-thing

    #.  If your branch is a fix for a release branch, choose that as the base
        branch (e.g. ``2016.11``),

        https://github.com/my-account/salt/compare/saltstack:2016.11...fix-broken-thing

        If your branch is a feature, choose ``|repo_primary_branch|`` as the base branch,

        https://github.com/my-account/salt/compare/saltstack:|repo_primary_branch|...add-cool-feature

    #.  Review that the proposed changes are what you expect.
    #.  Write a descriptive comment.  Include links to related issues (e.g.
        'Fixes #31337.') in the comment field.
    #.  Click ``Create pull request``.

#.  Salt project members will review your pull request and automated tests will
    run on it.

    If you recognize any test failures as being related to your proposed
    changes or if a reviewer asks for modifications:

    #.  Make the new changes in your local clone on the same local branch.
    #.  Push the branch to GitHub again using the same commands as before.
    #.  New and updated commits will be added to the pull request automatically.
    #.  Feel free to add a comment to the discussion.

.. note:: Jenkins

    Pull request against `saltstack/salt`_ are automatically tested on a
    variety of operating systems and configurations. On average these tests
    take 30 minutes.  Depending on your GitHub notification settings you may
    also receive an email message about the test results.

    Test progress and results can be found at http://jenkins.saltstack.com/.

.. _which-salt-branch:

Salt's Branch Topology
----------------------

There are three different kinds of branches in use: |repo_primary_branch|, main release
branches, and dot release branches.

- All feature work should go into the ``|repo_primary_branch|`` branch.
- Bug fixes and documentation changes should go into the oldest **supported
  main** release branch affected by the the bug or documentation change (you
  can use the blame button in github to figure out when the bug was introduced).
  Supported releases are the last 2 releases. For example, if the latest release
  is 2018.3, the last two release are 2018.3 and 2017.7.
  Main release branches are named after a year and month, such as
  ``2016.11`` and ``2017.7``.
- Hot fixes, as determined by SaltStack's release team, should be submitted
  against **dot** release branches. Dot release branches are named after a
  year, month, and version. Examples include ``2016.11.8`` and ``2017.7.2``.

.. note::

    GitHub will open pull requests against Salt's main branch, ``|repo_primary_branch|``,
    by default. Be sure to check which branch is selected when creating the
    pull request.

The |repo_primary_branch| Branch
================================

The ``|repo_primary_branch|`` branch is unstable and bleeding-edge. Pull requests containing
feature additions or non-bug-fix changes should be made against the ``|repo_primary_branch|``
branch.

.. note::

    If you have a bug fix or documentation change and have already forked your
    working branch from ``|repo_primary_branch|`` and do not know how to rebase your commits
    against another branch, then submit it to ``|repo_primary_branch|`` anyway. SaltStack's
    development team will be happy to back-port it to the correct branch.

    **Please make sure you let the maintainers know that the pull request needs
    to be back-ported.**

Main Release Branches
=====================

The current release branch is the most recent stable release. Pull requests
containing bug fixes or documentation changes should be made against the oldest supported main
release branch that is affected.

The branch name will be a date-based name such as ``2016.11``.

Bug fixes are made on this branch so that dot release branches can be cut from
the main release branch without introducing surprises and new features. This
approach maximizes stability.

Dot Release Branches
====================

Prior to tagging an official release, a branch will be created when the SaltStack
release team is ready to tag. The dot release branch is created from a main release
branch. The dot release branch will be the same name as the tag minus the ``v``.
For example, the ``2017.7.1`` dot release branch was created from the ``2017.7``
main release branch. The ``v2017.7.1`` release was tagged at the ``HEAD`` of the
``2017.7.1`` branch.

This branching strategy will allow for more stability when there is a need for
a re-tag during the testing phase of the release process and further increases
stability.

Once the dot release branch is created, the fixes required for a given release,
as determined by the SaltStack release team, will be added to this branch. All
commits in this branch will be merged forward into the main release branch as
well.

Merge Forward Process
=====================

The Salt repository follows a "Merge Forward" policy. The merge-forward
behavior means that changes submitted to older main release branches will
automatically be "merged-forward" into the newer branches.

For example, a pull request is merged into ``2017.7``. Then, the entire
``2017.7`` branch is merged-forward into the ``2018.3`` branch, and the
``2018.3`` branch is merged-forward into the ``|repo_primary_branch|`` branch.

This process makes is easy for contributors to make only one pull-request
against an older branch, but allows the change to propagate to all **main**
release branches.

The merge-forward work-flow applies to all main release branches and the
operation runs continuously.

Merge-Forwards for Dot Release Branches
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The merge-forward policy applies to dot release branches as well, but has a
slightly different behavior. If a change is submitted to a **dot** release
branch, the dot release branch will be merged into its parent **main**
release branch.

For example, a pull request is merged into the ``2017.7.2`` release branch.
Then, the entire ``2017.7.2`` branch is merged-forward into the ``2017.7``
branch. From there, the merge forward process continues as normal.

The only way in which dot release branches differ from main release branches
in regard to merge-forwards, is that once a dot release branch is created
from the main release branch, the dot release branch does not receive merge
forwards.

.. note::

    The merge forward process for dot release branches is one-way:
    dot release branch --> main release branch.

Closing GitHub issues from commits
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This "merge-forward" strategy requires that `the magic keywords to close a
GitHub issue <Closing issues via commit message_>`_ appear in the commit
message text directly. Only including the text in a pull request will not
close the issue.

GitHub will close the referenced issue once the *commit* containing the
magic text is merged into the default branch (``|repo_primary_branch|``). Any magic text
input only into the pull request description will not be seen at the
Git-level when those commits are merged-forward. In other words, only the
commits are merged-forward and not the pull request text.

.. _backporting-pull-requests:

Backporting Pull Requests
=========================

If a bug is fixed on ``|repo_primary_branch|`` and the bug is also present on a
currently-supported release branch, it will need to be back-ported to an
applicable branch.

.. note:: Most Salt contributors can skip these instructions

    These instructions do not need to be read in order to contribute to the
    Salt project! The SaltStack team will back-port fixes on behalf of
    contributors in order to keep the contribution process easy.

    These instructions are intended for frequent Salt contributors, advanced
    Git users, SaltStack employees, or independent souls who wish to back-port
    changes themselves.

It is often easiest to fix a bug on the oldest supported release branch and
then merge that branch forward into ``|repo_primary_branch|`` (as described earlier in this
document). When that is not possible the fix must be back-ported, or copied,
into any other affected branches.

These steps assume a pull request ``#1234`` has been merged into ``|repo_primary_branch|``.
And ``upstream`` is the name of the remote pointing to the main Salt repo.

#.  Identify the oldest supported release branch that is affected by the bug.

#.  Create a new branch for the back-port by reusing the same branch from the
    original pull request.

    Name the branch ``bp-<NNNN>`` and use the number of the original pull
    request.

    .. code-block:: bash

        git fetch upstream refs/pull/1234/head:bp-1234
        git checkout bp-1234

#.  Find the parent commit of the original pull request.

    The parent commit of the original pull request must be known in order to
    rebase onto a release branch. The easiest way to find this is on GitHub.

    Open the original pull request on GitHub and find the first commit in the
    list of commits. Select and copy the SHA for that commit. The parent of
    that commit can be specified by appending ``~1`` to the end.

#.  Rebase the new branch on top of the release branch.

    * ``<release-branch>`` is the branch identified in step #1.

    * ``<orig-base>`` is the SHA identified in step #3 -- don't forget to add
      ``~1`` to the end!

    .. code-block:: bash

        git rebase --onto <release-branch> <orig-base> bp-1234

    Note, release branches prior to ``2016.11`` will not be able to make use of
    rebase and must use cherry-picking instead.

#.  Push the back-port branch to GitHub and open a new pull request.

    Opening a pull request for the back-port allows for the test suite and
    normal code-review process.

    .. code-block:: bash

        git push -u origin bp-1234

Keeping Salt Forks in Sync
--------------------------

Salt advances quickly. It is therefore critical to pull upstream changes
from upstream into your fork on a regular basis. Nothing is worse than putting
hard work into a pull request only to see bunches of merge conflicts because it
has diverged too far from upstream.

.. seealso:: `GitHub Fork a Repo Guide`_

The following assumes ``origin`` is the name of your fork and ``upstream`` is
the name of the main `saltstack/salt`_ repository.

#.  View existing remotes.

    .. code-block:: bash

        git remote -v

#.  Add the ``upstream`` remote.

    .. code-block:: bash

        # For ssh github
        git remote add upstream git@github.com:saltstack/salt.git

        # For https github
        git remote add upstream https://github.com/saltstack/salt.git

#.  Pull upstream changes into your clone.

    .. code-block:: bash

        git fetch upstream

#.  Update your copy of the ``|repo_primary_branch|`` branch.

    .. code-block:: bash

        git checkout |repo_primary_branch|
        git merge --ff-only upstream/|repo_primary_branch|

    If Git complains that a fast-forward merge is not possible, you have local
    commits.

    * Run ``git pull --rebase origin |repo_primary_branch|`` to rebase your changes on top of
      the upstream changes.
    * Or, run ``git branch <branch-name>`` to create a new branch with your
      commits. You will then need to reset your ``|repo_primary_branch|`` branch before
      updating it with the changes from upstream.

    If Git complains that local files will be overwritten, you have changes to
    files in your working directory. Run ``git status`` to see the files in
    question.

#.  Update your fork.

    .. code-block:: bash

        git push origin |repo_primary_branch|

#.  Repeat the previous two steps for any other branches you work with, such as
    the current release branch.

Posting patches to the mailing list
-----------------------------------

Patches will also be accepted by email. Format patches using `git
format-patch`_ and send them to the `salt-users`_ mailing list. The contributor
will then get credit for the patch, and the Salt community will have an archive
of the patch and a place for discussion.

Issue and Pull Request Labeling System
--------------------------------------

SaltStack uses several labeling schemes to help facilitate code contributions
and bug resolution. See the :ref:`Labels and Milestones
<labels-and-milestones>` documentation for more information.

Mentionbot
----------

SaltStack runs a mention-bot which notifies contributors who might be able
to help review incoming pull-requests based on their past contribution to
files which are being changed.

If you do not wish to receive these notifications, please add your GitHub
handle to the blacklist line in the ``.mention-bot`` file located in the
root of the Salt repository.

.. _probot-gpg-verification:

GPG Verification
----------------

SaltStack has enabled `GPG Probot`_ to enforce GPG signatures for all
commits included in a Pull Request.

In order for the GPG verification status check to pass, *every* contributor in
the pull request must:

- Set up a GPG key on local machine
- Sign all commits in the pull request with key
- Link key with GitHub account

This applies to all commits in the pull request.

GitHub hosts a number of `help articles`_ for creating a GPG key, using the
GPG key with ``git`` locally, and linking the GPG key to your GitHub account.
Once these steps are completed, the commit signing verification will look like
the example in GitHub's `GPG Signature Verification feature announcement`_.

Bootstrap Script Changes
------------------------

Salt's Bootstrap Script, known as `bootstrap-salt.sh`_ in the Salt repo, has it's own
repository, contributing guidelines, and release cadence.

All changes to the Bootstrap Script should be made to `salt-bootstrap repo`_. Any
pull requests made to the `bootstrap-salt.sh`_ file in the Salt repository will be
automatically overwritten upon the next stable release of the Bootstrap Script.

For more information on the release process or how to contribute to the Bootstrap
Script, see the Bootstrap Script's `Contributing Guidelines`_.

.. _`saltstack/salt`: https://github.com/saltstack/salt
.. _`GitHub Fork a Repo Guide`: https://help.github.com/articles/fork-a-repo
.. _`issue tracker`: https://github.com/saltstack/salt/issues
.. _`Fork saltstack/salt`: https://github.com/saltstack/salt/fork
.. _'Git resources`: https://help.github.com/articles/good-resources-for-learning-git-and-github/
.. _`Closing issues via commit message`: https://help.github.com/articles/closing-issues-via-commit-messages
.. _`git format-patch`: https://www.kernel.org/pub/software/scm/git/docs/git-format-patch.html
.. _salt-users: https://groups.google.com/forum/#!forum/salt-users
.. _GPG Probot: https://probot.github.io/apps/gpg/
.. _help articles: https://help.github.com/articles/signing-commits-with-gpg/
.. _GPG Signature Verification feature announcement: https://github.com/blog/2144-gpg-signature-verification
.. _bootstrap-salt.sh: https://github.com/saltstack/salt/blob/|repo_primary_branch|/salt/cloud/deploy/bootstrap-salt.sh
.. _salt-bootstrap repo: https://github.com/saltstack/salt-bootstrap
.. _Contributing Guidelines: https://github.com/saltstack/salt-bootstrap/blob/develop/CONTRIBUTING.md
