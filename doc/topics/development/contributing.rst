.. _contributing:

============
Contributing
============

There is a great need for contributions to Salt and patches are welcome! The
goal here is to make contributions clear, make sure there is a trail for where
the code has come from, and most importantly, to give credit where credit is
due!

There are a number of ways to contribute to Salt development, including (but
not limited to):

* filing well-written bug reports
* enhancing the documentation
* providing workarounds, patches, and other code without tests
* engaging in constructive discussion
* helping out in `#salt on Freenode <#salt on freenode_>`_,
  the `Community Slack <SaltStack Community Slack_>`_,
  the `salt-users <salt-users_>`_ mailing list,
  a `SaltStack meetup <saltstack meetup_>`_,
  or `Server Fault <saltstack on serverfault_>`_.
* telling others about problems you solved with Salt

If this or other Salt documentation is unclear, please review :ref:`Writing
Salt Documentation <salt-docs>`. PRs are welcome!


Quickstart
----------

If you just want to get started before reading the rest of this guide, you can
get the process started by running the following:

.. code-block:: bash

    python3 -m pip install --user pre-commit
    git clone --origin upstream https://github.com/saltstack/salt.git
    cd salt
    pre-commit install

While those commands are running, finish reading the rest of this guide.


Pre-commit
----------

To reduce friction during the development process, SaltStack uses `pre-commit
<pre-commit_>`_. This tool adds pre-commit hooks to git to automate several
processes that used to be manual. Rather than having to remember to run several
different tools before you commit, you only have to run ``git commit``, and you
will be notified about style and lint issues before you ever open a PR.


Salt Coding Style
-----------------

After the 3000 release, SaltStack is `joining the ranks <SEP 15_>`_ of projects
in adopting the `Black code formatter <Black_>`_ in order to ease the adoption
of a unified code formatting style.

Where Black is silent, SaltStack has its own coding style guide that informs
contributors on various style points. Please review the :ref:`Salt Coding Style
<coding-style>` documentation for information about Salt's particular coding
patterns.

Within the :ref:`Salt Coding Style <coding-style>` documentation, there is a
section about running Salt's ``.testing.pylintrc`` file. SaltStack recommends
running the ``.testing.pylintrc`` file on any files you are changing with your
code contribution before submitting a pull request to Salt's repository.

If you've installed ``pre-commit``, this will automatically happen before each
commit.  Otherwise, see the :ref:`Linting<pylint-instructions>` documentation
for more information.


Copyright Headers
-----------------

Copyright headers are not needed for files in the Salt project. Files that have
existing copyright headers should be considered legacy and not an example to
follow.

.. _github-pull-request:

Sending a GitHub pull request
-----------------------------

Sending pull requests on GitHub is the preferred method for receiving
contributions. The workflow advice below mirrors `GitHub's own guide <GitHub
Fork a Repo Guide_>`_ and is well worth reading.

#.  `Fork saltstack/salt`_ on GitHub.
#.  Make a local clone of your fork. (Skip this step if you followed
    the Quickstart)

    .. code-block:: bash

         git clone git@github.com:my-account/salt.git
         cd salt

#.  Add `saltstack/salt`_ as a git remote.

    .. code-block:: bash

         git remote add upstream https://github.com/saltstack/salt.git

    If you followed the Quickstart, you'll add your own remote instead

    .. code-block:: bash

         git remote add my-account git@github.com:my-account/salt.git

#.  Create a new branch in your clone.

    .. note::

        A branch should have one purpose. For example, "Fix bug X," or "Add
        feature Y".  Multiple unrelated fixes and/or features should be
        isolated into separate branches.

    .. code-block:: bash

        git fetch upstream
        git checkout -b fix-broken-thing upstream/master

#.  Edit and commit changes to your branch.

    .. code-block:: bash

        vim path/to/file1 path/to/file2 tests/test_file1.py tests/test_file2.py
        git diff
        git add path/to/file1 path/to/file2
        git commit

    Write a short, descriptive commit title and a longer commit message if
    necessary. Use an imperative style for the title.

    GOOD

    .. code-block::

        Fix broken things in file1 and file2

        Fixes #31337

        We needed to make this change because the underlying dependency
        changed. Now this uses the up-to-date API.

        # Please enter the commit message for your changes. Lines starting
        # with '#' will be ignored, and an empty message aborts the commit.
        # On branch fix-broken-thing
        # Changes to be committed:
        #       modified:   path/to/file1
        #       modified:   path/to/file2

    BAD

    .. code-block::

        Fixes broken things

        # Please enter the commit message for your changes. Lines starting
        # with '#' will be ignored, and an empty message aborts the commit.
        # On branch fix-broken-thing
        # Changes to be committed:
        #       modified:   path/to/file1
        #       modified:   path/to/file2

    Taking a few moments to explain *why* you made a change will save time
    and effort in the future when others come to investigate a change. A
    clear explanation of why something changed can help future developers
    avoid introducing bugs, or breaking an edge case.

    .. note::

        If your change fixes a bug or implements a feature already filed in the
        `issue tracker`_, be sure to
	`reference the issue <https://help.github.com/en/articles/closing-issues-using-keywords>`_
        number in the commit message body.

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
            git rebase upstream/master fix-broken-thing
            git push -u origin fix-broken-thing

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

    #.  Choose ``master`` as the base Salt branch.
    #.  Review that the proposed changes are what you expect.
    #.  Write a descriptive comment. If you added good information to your git
        commit message, they will already be present here. Include links to
        related issues (e.g. 'Fixes #31337.') in the comment field.
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
    take a couple of hours.  Depending on your GitHub notification settings
    you may also receive an email message about the test results.

    Test progress and results can be found at http://jenkins.saltstack.com/.

.. _which-salt-branch:

Salt's Branch Topology
----------------------

Salt will only have one active branch - ``master``.
This will include bug fixes, features and CVE “Common Vulnerabilities and Exposures”.

The release will be cut from the master when the time comes for a new release,
which should be every 3 to 4 months.

To be able to merge code:

    #. The code must have a well-written test.
       Note that you are only expected to write tests for what you did, not the whole modules or function.

    #. All tests must pass.

The SaltStack employee that reviews your pull request might request changes or deny the pull request for various reasons.

Salt uses a typical branch strategy - ``master`` is the next expected release.
Code should only make it to ``master`` once it's production ready. This means
that typical changes (fixes, features) should have accompanying tests.\

Closing GitHub issues from commits
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

SaltStack encourages using `the magic keywords to close a GitHub issue <Closing
issues via commit message_>`_. These should appear in the commit message text
directly.


Release Naming Convention
-------------------------

A new convention will start when Salt releases Salt 3000.
Every new release name will increment by one ‘Salt last_release_number + 1’.

This naming convention is very different from past releases, which was 'YYYY.MM.PATCH'.

Handling CVE
--------------

If a CVE is discovered, Salt will create a new release that **only** contains the tests and patch for the CVE.
This method should improve the upgrade process by reducing the chances of breaking something.

.. _backporting-pull-requests:


Backporting Pull Requests
-------------------------

On rare occasions, a serious bug will be found in the middle of a release
cycle. These bugs will require a point release. Contributors should still
submit fixes directly to ``master``, but they should also call attention to the
fact that it addresses a critical issue and will need to be back-ported.

Keeping Salt Forks in Sync
--------------------------

Salt advances quickly. It is therefore critical to pull upstream changes from
upstream into your fork on a regular basis. Nothing is worse than putting hard
work into a pull request only to see bunches of merge conflicts because it has
diverged too far from upstream.

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

#.  Update your copy of the ``master`` branch.

    .. code-block:: bash

        git checkout master
        git merge --ff-only upstream/master

    If Git complains that a fast-forward merge is not possible, you have local
    commits.

    * Run ``git pull --rebase origin master`` to rebase your changes on top of
      the upstream changes.
    * Or, run ``git branch <branch-name>`` to create a new branch with your
      commits. You will then need to reset your ``master`` branch before
      updating it with the changes from upstream.

    If Git complains that local files will be overwritten, you have changes to
    files in your working directory. Run ``git status`` to see the files in
    question.

#.  Update your fork.

    .. code-block:: bash

        git push origin master

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
.. _bootstrap-salt.sh: https://github.com/saltstack/salt/blob/master/salt/cloud/deploy/bootstrap-salt.sh
.. _salt-bootstrap repo: https://github.com/saltstack/salt-bootstrap
.. _Contributing Guidelines: https://github.com/saltstack/salt-bootstrap/blob/develop/CONTRIBUTING.md
.. _`Black`: https://pypi.org/project/black/
.. _`SEP 15`: https://github.com/saltstack/salt-enhancement-proposals/pull/21
.. _`pre-commit`: https://pre-commit.com/
.. _`SaltStack Community Slack`: https://saltstackcommunity.herokuapp.com/
.. _`#salt on freenode`: http://webchat.freenode.net/?channels=salt&uio=Mj10cnVlJjk9dHJ1ZSYxMD10cnVl83
.. _`saltstack meetup`: https://www.meetup.com/pro/saltstack/
.. _`saltstack on serverfault`: https://serverfault.com/questions/tagged/saltstack
