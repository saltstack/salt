Contributing
============

There is a great need for contributions to Salt and patches are welcome! The goal
here is to make contributions clear, make sure there is a trail for where the code
has come from, and most importantly, to give credit where credit is due!

There are a number of ways to contribute to salt development.


Sending a GitHub pull request
-----------------------------

This is the preferred method for contributions. Simply create a GitHub
fork, commit changes to the fork, and then open up a pull request.

The following is an example (from `Open Comparison Contributing Docs`_ )
of an efficient workflow for forking, cloning, branching, committing, and
sending a pull request for a GitHub repository.

First, make a local clone of your GitHub fork of the salt GitHub repo and make
edits and changes locally.

Then, create a new branch on your clone by entering the following commands:

.. code-block:: bash

    git checkout -b fixed-broken-thing

    Switched to a new branch 'fixed-broken-thing'

Choose a name for your branch that describes its purpose.

Now commit your changes to this new branch with the following command:

.. code-block:: bash

    git commit -am 'description of my fixes for the broken thing'

.. note::

    Using ``git commit -am``, followed by a quoted string, both stages and
    commits all modified files in a single command. Depending on the nature of
    your changes, you may wish to stage and commit them separately. Also, note
    that if you wish to add newly-tracked files as part of your commit, they
    will not be caught using ``git commit -am`` and will need to be added using
    ``git add`` before committing.

Push your locally-committed changes back up to GitHub:

.. code-block:: bash

    git push --set-upstream origin fixed-broken-thing

Now go look at your fork of the salt repo on the GitHub website. The new
branch will now be listed under the "Source" tab where it says "Switch Branches".
Select the new branch from this list, and then click the "Pull request" button.

Put in a descriptive comment, and include links to any project issues related
to the pull request.

The repo managers will be notified of your pull request and it will be
reviewed. If a reviewer asks for changes, just make the changes locally in the
same local feature branch, push them to GitHub, then add a comment to the
discussion section of the pull request.

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

.. note:: Minor releases

    Minor releases normally contain bug fixes selected by the Salt core
    development team.

    When submitting a pull-request which should be considered for a minor
    release, please note in the comments that it should be reviewed
    for inclusion.

    Pull requests that are accepted to Salt but not merged into a minor
    release will always be available in the next major release.

Keeping Salt Forks in Sync
--------------------------

Salt is advancing quickly. It is therefore critical to pull upstream changes
from master into forks on a regular basis. Nothing is worse than putting in a
days of hard work into a pull request only to have it rejected because it has
diverged too far from master.

To pull in upstream changes:

.. code-block:: bash

    # For ssh github
    git remote add upstream git@github.com:saltstack/salt.git
    git fetch upstream

    # For https github
    git remote add upstream https://github.com/saltstack/salt.git
    git fetch upstream


To check the log to be sure that you actually want the changes, run the
following before merging:

.. code-block:: bash

    git log upstream/develop

Then to accept the changes and merge into the current branch:

.. code-block:: bash

    git merge upstream/develop

For more info, see `GitHub Fork a Repo Guide`_ or `Open Comparison Contributing
Docs`_

.. _`GitHub Fork a Repo Guide`: https://help.github.com/articles/fork-a-repo
.. _`Open Comparison Contributing Docs`: http://opencomparison.readthedocs.org/en/latest/contributing.html

Posting patches to the mailing list
-----------------------------------

Patches will also be accepted by email. Format patches using `git
format-patch`_ and send them to the Salt users mailing list. The contributor
will then get credit for the patch, and the Salt community will have an archive
of the patch and a place for discussion.

.. _`git format-patch`: https://www.kernel.org/pub/software/scm/git/docs/git-format-patch.html

