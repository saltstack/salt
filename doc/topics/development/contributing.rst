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

    If you're working on a feature, create your branch from the master branch.

    .. code-block:: bash

        git fetch upstream
        git checkout -b add-cool-feature upstream/master

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

        https://github.com/my-account/salt/compare/saltstack:master...add-cool-feature

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

Salt will only be active on one branch which is master.
This will include bug fixes, features and CVE “Common Vulnerabilities and Exposures”.

When the time comes for a new release which should be every 3 to 4 months
the release will be cut from the master.

To be able to merge code. The code must have well written test.
Please note you are only expected to write test for what you did not the whole modules or function.
All tests must also pass.
The salt stack employee that reviews your pull request might
request changes or deny the pull request for various reasons.

Release Naming Convention
-------------------------

A new convention will start when Salt releases Salt 3000.
Every new release name will increment by one ‘Salt last_release_number + 1’.

This is very different from past releases which was 'year, month, dot release'.
For example 2019.2 and 2019.2.3.

Handling CVE’s
--------------

Salt will make a new release identical to its last.
The only difference will be the path/fix for the CVE.
This should make the upgrade process a lot smoother for people
because the odds of something breaking is a lot smaller.

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
