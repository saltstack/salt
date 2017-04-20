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
approaches. Please review the :ref:`Salt Coding Style<coding-style>` documentation
for information about Salt's particular coding patterns.

Within the :ref:`Salt Coding Style<coding-style>` documentation, there is a section
about running Salt's ``.pylintrc`` file. SaltStack recommends running the ``.pylintrc``
file on any files you are changing with your code contribution before submitting a
pull request to Salt's repository. Please see the :ref:`Linting<pylint-instructions>`
documentation for more information.


.. _github-pull-request:

Sending a GitHub pull request
=============================

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
    the oldest release branch that contains the bug or requires the documentation
    update. See :ref:`Which Salt Branch? <which-salt-branch>`.

    .. code-block:: bash

        git fetch upstream
        git checkout -b fix-broken-thing upstream/2016.3

    If you're working on a feature, create your branch from the develop branch.

    .. code-block:: bash

        git fetch upstream
        git checkout -b add-cool-feature upstream/develop

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
        `issue tracker <GitHub issue tracker>`_, be sure to reference the issue
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
            git rebase upstream/2016.3 fix-broken-thing
            git push -u origin fix-broken-thing

        or

        .. code-block:: bash

            git fetch upstream
            git rebase upstream/develop add-cool-feature
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
        ``--force`` to the end of the ``git push`` command to get the changes
        pushed to your fork. Pulling or merging, while they will resolve the
        non-fast-forward issue, will likely add extra commits to the pull
        request which were not part of your changes.

#.  Find the branch on your GitHub salt fork.

    https://github.com/my-account/salt/branches/fix-broken-thing

#.  Open a new pull request.

    Click on ``Pull Request`` on the right near the top of the page,

    https://github.com/my-account/salt/pull/new/fix-broken-thing

    #.  If your branch is a fix for a release branch, choose that as the base
        branch (e.g. ``2016.3``),

        https://github.com/my-account/salt/compare/saltstack:2016.3...fix-broken-thing

        If your branch is a feature, choose ``develop`` as the base branch,

        https://github.com/my-account/salt/compare/saltstack:develop...add-cool-feature

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

Which Salt branch?
==================

GitHub will open pull requests against Salt's main branch, ``develop``, by
default. Ideally, features should go into ``develop`` and bug fixes and
documentation changes should go into the oldest supported release branch
affected by the bug or documentation update.  See
:ref:`Sending a GitHub pull request <github-pull-request>`.

If you have a bug fix or doc change and have already forked your working
branch from ``develop`` and do not know how to rebase your commits against
another branch, then submit it to ``develop`` anyway and we'll be sure to
back-port it to the correct place.

The current release branch
--------------------------

The current release branch is the most recent stable release. Pull requests
containing bug fixes should be made against the release branch.

The branch name will be a date-based name such as ``2016.3``.

Bug fixes are made on this branch so that minor releases can be cut from this
branch without introducing surprises and new features. This approach maximizes
stability.

The Salt development team will "merge-forward" any fixes made on the release
branch to the ``develop`` branch once the pull request has been accepted. This
keeps the fix in isolation on the release branch and also keeps the ``develop``
branch up-to-date.

.. note:: Closing GitHub issues from commits

    This "merge-forward" strategy requires that `the magic keywords to close a
    GitHub issue <Closing issues via commit message_>`_ appear in the commit
    message text directly. Only including the text in a pull request will not
    close the issue.

    GitHub will close the referenced issue once the *commit* containing the
    magic text is merged into the default branch (``develop``). Any magic text
    input only into the pull request description will not be seen at the
    Git-level when those commits are merged-forward. In other words, only the
    commits are merged-forward and not the pull request.

The ``develop`` branch
----------------------

The ``develop`` branch is unstable and bleeding-edge. Pull requests containing
feature additions or non-bug-fix changes should be made against the ``develop``
branch.

The Salt development team will back-port bug fixes made to ``develop`` to the
current release branch if the contributor cannot create the pull request
against that branch.

Keeping Salt Forks in Sync
==========================

Salt is advancing quickly. It is therefore critical to pull upstream changes
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

#.  Update your copy of the ``develop`` branch.

    .. code-block:: bash

        git checkout develop
        git merge --ff-only upstream/develop

    If Git complains that a fast-forward merge is not possible, you have local
    commits.

    * Run ``git pull --rebase origin develop`` to rebase your changes on top of
      the upstream changes.
    * Or, run ``git branch <branch-name>`` to create a new branch with your
      commits. You will then need to reset your ``develop`` branch before
      updating it with the changes from upstream.

    If Git complains that local files will be overwritten, you have changes to
    files in your working directory. Run ``git status`` to see the files in
    question.

#.  Update your fork.

    .. code-block:: bash

        git push origin develop

#.  Repeat the previous two steps for any other branches you work with, such as
    the current release branch.

Posting patches to the mailing list
===================================

Patches will also be accepted by email. Format patches using `git
format-patch`_ and send them to the `salt-users`_ mailing list. The contributor
will then get credit for the patch, and the Salt community will have an archive
of the patch and a place for discussion.

.. _backporting-pull-requests:

Backporting Pull Requests
=========================

If a bug is fixed on ``develop`` and the bug is also present on a
currently-supported release branch it will need to be back-ported to all
applicable branches.

.. note:: Most Salt contributors can skip these instructions

    These instructions do not need to be read in order to contribute to the
    Salt project! The SaltStack team will back-port fixes on behalf of
    contributors in order to keep the contribution process easy.

    These instructions are intended for frequent Salt contributors, advanced
    Git users, SaltStack employees, or independent souls who wish to back-port
    changes themselves.

It is often easiest to fix a bug on the oldest supported release branch and
then merge that branch forward into ``develop`` (as described earlier in this
document). When that is not possible the fix must be back-ported, or copied,
into any other affected branches.

These steps assume a pull request ``#1234`` has been merged into ``develop``.
And ``upstream`` is the name of the remote pointing to the main Salt repo.

1.  Identify the oldest supported release branch that is affected by the bug.

2.  Create a new branch for the back-port by reusing the same branch from the
    original pull request.

    Name the branch ``bp-<NNNN>`` and use the number of the original pull
    request.

    .. code-block:: bash

        git fetch upstream refs/pull/1234/head:bp-1234
        git checkout bp-1234

3.  Find the parent commit of the original pull request.

    The parent commit of the original pull request must be known in order to
    rebase onto a release branch. The easiest way to find this is on GitHub.

    Open the original pull request on GitHub and find the first commit in the
    list of commits. Select and copy the SHA for that commit. The parent of
    that commit can be specified by appending ``~1`` to the end.

4.  Rebase the new branch on top of the release branch.

    * ``<release-branch>`` is the branch identified in step #1.

    * ``<orig-base>`` is the SHA identified in step #3 -- don't forget to add
      ``~1`` to the end!

    .. code-block:: bash

        git rebase --onto <release-branch> <orig-base> bp-1234

    Note, release branches prior to ``2016.3`` will not be able to make use of
    rebase and must use cherry-picking instead.

5.  Push the back-port branch to GitHub and open a new pull request.

    Opening a pull request for the back-port allows for the test suite and
    normal code-review process.

    .. code-block:: bash

        git push -u origin bp-1234

Issue and Pull Request Labeling System
======================================

SaltStack uses several labeling schemes to help facilitate code contributions
and bug resolution. See the :ref:`Labels and Milestones
<labels-and-milestones>` documentation for more information.

.. _`saltstack/salt`: https://github.com/saltstack/salt
.. _`GitHub Fork a Repo Guide`: https://help.github.com/articles/fork-a-repo
.. _`GitHub issue tracker`: https://github.com/saltstack/salt/issues
.. _`Fork saltstack/salt`: https://github.com/saltstack/salt/fork
.. _'Git resources`: https://help.github.com/articles/good-resources-for-learning-git-and-github/
.. _`Closing issues via commit message`: https://help.github.com/articles/closing-issues-via-commit-messages
.. _`git format-patch`: https://www.kernel.org/pub/software/scm/git/docs/git-format-patch.html

Mentionbot
==========

SaltStack runs a mention-bot which notifies contributors who might be able
to help review incoming pull-requests based on their past contribution to
files which are being changed.

If you do not wish to receive these notifications, please add your GitHub
handle to the blacklist line in the `.mention-bot` file located in the
root of the Salt repository.
