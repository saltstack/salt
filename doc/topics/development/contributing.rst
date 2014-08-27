============
Contributing
============

There is a great need for contributions to Salt and patches are welcome! The goal
here is to make contributions clear, make sure there is a trail for where the code
has come from, and most importantly, to give credit where credit is due!

There are a number of ways to contribute to Salt development.

For details on how to contribute documentation improvements please review
:ref:`Writing Salt Documentation <salt-docs>`.

Sending a GitHub pull request
=============================

Sending pull requests on GitHub is the preferred method for receiving
contributions. The workflow advice below mirrors `GitHub's own guide <GitHub
Fork a Repo Guide>`_ and is well worth reading.

#.  Fork the `saltstack/salt`_ repository on GitHub.
#.  Make a local clone of your fork.
#.  Create a new branch in your clone.

    A branch should have one purpose. For example, "Fix bug X," or "Add feature
    Y." Multiple pull requests should be opened for unrelated changes.

    Choose a name for your branch that describes its purpose.

    .. code-block:: bash

        git checkout -b fixed-broken-thing

#.  Make edits and changes locally.
#.  Commit changes to this new branch.

    Edit the necessary files in your Salt clone and remember to add them to
    your commit. Write a descriptive commit message.

    .. code-block:: bash

        git add path/to/file1
        git add path/to/file2
        git commit -m "Fixed X in file1 and file2"

    If you get stuck `there are many introductory Git resources on
    help.github.com <Git resources>`_.

#.  Push your locally-committed changes to your GitHub fork.

    .. code-block:: bash

        git push --set-upstream origin fixed-broken-thing

#.  Go to your fork on the GitHub website & find your branch.

    GitHub automatically displays a button with the text "Compare & pull
    request" for recently pushed branches.

    Otherwise click on the "Branches" tab at the top of your fork. A button
    with the text "New pull request" will be beside each branch.

#.  Open a new pull request.

    #.  Click one of the pull request buttons from the previous step. GitHub
        will present a form and show a comparison of the changes in your pull
        request.
    #.  Write a descriptive comment, include links to any project issues
        related to the pull request.
    #.  Click "Create pull request".

#.  The Salt repo managers will be notified of your pull request.
   
    If a reviewer asks for changes:

    #.  Make the changes in your local clone on the same local branch.
    #.  Push the branch to GitHub using the same command as before.
    #.  The new commits will be reflected in the pull request automatically.
    #.  Feel free to add a comment to the discussion.

.. note:: Jenkins

    Whenever you make a pull request against the main Salt repository your
    changes will be tested on a variety of operating systems and
    configurations. On average these tests take 30 minutes to run and once
    they are complete a PASS/FAIL message will be added to your pull
    request. This message contains a link to http://jenkins.saltstack.com
    where you can review the test results. This message will also generate an
    email which will be sent to the email address associated with your GitHub
    account informing you of these results. It should be noted that a test
    failure does not necessarily mean there is an issue in the associated pull
    request as the entire development branch is tested.

Which Salt branch?
==================

GitHub will open pull requests against Salt's main branch named ``develop`` by
default. Most contributors can keep the default options. This section is for
advanced contributors.

Each pull request should address a single concern, as mentioned in the section
above. For example, "Fix bug X," or "Add feature Y." And a pull request should
be opened against the branch that corresponds to that concern.

The current release branch
--------------------------

The current release branch is the most recent stable release. Pull requests
containing bug fixes should be made against the release branch.

The branch name will be a date-based name such as ``2014.7``.

Bug fixes are made on this branch so that minor releases can be cut from this
branch without introducing surprises and new features. This approach maximizes
stability.

The Salt development team will "merge-forward" any fixes made on the release
branch to the ``develop`` branch once the pull request has been accepted. This
keeps the fix in isolation on the release branch and also keeps the ``develop``
branch up-to-date.

.. note:: Closing GitHub issues from commits

    This "merge-forward" strategy requires that `the magic keywords to close a
    GitHub issue <Closing issues via commit message>`_ appear in the commit
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

    Note, release branches prior to ``2014.7`` will not be able to make use of
    rebase and must use cherry-picking instead.

5.  Push the back-port branch to GitHub and open a new pull request.

    Opening a pull request for the back-port allows for the test suite and
    normal code-review process.

    .. code-block:: bash

        git push -u origin bp-1234

.. _`saltstack/salt`: https://github.com/saltstack/salt
.. _`GitHub Fork a Repo Guide`: https://help.github.com/articles/fork-a-repo
.. _`Git resources`: https://help.github.com/articles/what-are-other-good-resources-for-learning-git-and-github
.. _`Closing issues via commit message`: https://help.github.com/articles/closing-issues-via-commit-messages
.. _`git format-patch`: https://www.kernel.org/pub/software/scm/git/docs/git-format-patch.html
