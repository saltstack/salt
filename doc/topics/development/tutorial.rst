.. _developing-tutorial:

========================
Developing Salt Tutorial
========================

This tutorial assumes you have:

* a web browser
* a GitHub account (``<my_account>``)
* a command line (CLI)
* git
* a text editor

----
Fork
----

In your browser, navigate to the ``saltstack/salt`` `GitHub repository
<https://github.com/saltstack/salt>`_.

Click on ``Fork`` (https://github.com/saltstack/salt/#fork-destination-box).

.. note::

    If you have more than one GitHub presence, for example if you are a member
    of a team, GitHub will ask you into which area to clone Salt.  If you don't
    know where, then select your personal GitHub account.

-----
Clone
-----

In your CLI, navigate to the directory into which you want clone the Salt
codebase and submit the following command:

.. code-block:: bash

    $ git clone https://github.com/<my_account>/salt.git

where ``<my_account>`` is the name of your GitHub account.  After the clone has
completed, add SaltStack as a second remote and fetch any changes from
``upstream``.

.. code-block:: bash

    $ cd salt
    $ git remote add upstream https://github.com/saltstack/salt.git
    $ git fetch upstream

For this tutorial, we will be working off from the ``|repo_primary_branch|`` branch, which is
the default branch for the SaltStack GitHub project.  This branch needs to
track ``upstream/|repo_primary_branch|`` so that we will get all upstream changes when they
happen.

.. code-block:: bash

    $ git checkout |repo_primary_branch|
    $ git branch --set-upstream-to upstream/|repo_primary_branch|

-----
Fetch
-----

Fetch any ``upstream`` changes on the ``|repo_primary_branch|`` branch and sync them to your
local copy of the branch with a single command:

.. code-block:: bash

    $ git pull --rebase

.. note::

    For an explanation on ``pull`` vs ``pull --rebase`` and other excellent
    points, see `this article <http://mislav.net/2013/02/merge-vs-rebase/>`_ by
    Mislav Marohnić.

------
Branch
------

Now we are ready to get to work.  Consult the `sprint beginner bug list
<https://github.com/saltstack/salt/wiki/December-2015-Sprint-Beginner-Bug-List>`_
and select an execution module whose ``__virtual__`` function needs to be
updated.  I'll select the ``alternatives`` module.

Create a new branch off from ``|repo_primary_branch|``.  Be sure to name it something short
and descriptive.

.. code-block:: bash

    $ git checkout -b virt_ret

----
Edit
----

Edit the file you have selected, and verify that the changes are correct.

.. code-block:: bash

    $ vim salt/modules/alternatives.py
    $ git diff

.. code-block:: diff

    diff --git a/salt/modules/alternatives.py b/salt/modules/alternatives.py
    index 1653e5f..30c0a59 100644
    --- a/salt/modules/alternatives.py
    +++ b/salt/modules/alternatives.py
    @@ -30,7 +30,7 @@ def __virtual__():
             '''
             if os.path.isdir('/etc/alternatives'):
                     return True
    -        return False
    +        return (False, 'Cannot load alternatives module: /etc/alternatives dir not found')


     def _get_cmd():

------
Commit
------

Stage and commit the changes.  Write a descriptive commit summary, but try to
keep it less than 50 characters.  Review your commit.

.. code-block:: bash

    $ git add salt/modules/alternatives.py
    $ git commit -m 'modules.alternatives: __virtual__ return err msg'
    $ git show

.. note::

    If you need more room to describe the changes in your commit, run ``git
    commit`` (without the ``-m``, message, option) and you will be presented
    with an editor.  The first line is the commit summary and should still be
    50 characters or less.  The following paragraphs you create are free form
    and will be preserved as part of the commit.

----
Push
----

Push your branch to your GitHub account.  You will likely need to enter your
GitHub username and password.

.. code-block:: bash

    $ git push origin virt_ret
    Username for 'https://github.com': <my_account>
    Password for 'https://<my_account>@github.com':

.. note::

    If authentication over https does not work, you can alternatively setup
    `ssh keys <https://help.github.com/articles/generating-ssh-keys/>`_.  Once
    you have done this, you may need add the keys to your git repository
    configuration

    .. code-block:: bash

        $ git config ssh.key ~/.ssh/<key_name>

    where ``<key_name>`` is the file name of the private key you created.

-----
Merge
-----

In your browser, navigate to the `new pull request
<https://github.com/saltstack/salt/compare>`_ page on the ``saltstack/salt``
GitHub repository and click on ``compare across forks``.  Select
``<my_account>`` from the list of head forks and the branch you are wanting to
merge into ``|repo_primary_branch|`` (``virt_ret`` in this case).

When you have finished reviewing the changes, click ``Create pull request``.

If your pull request contains only a single commit, the title and comment will
be taken from that commit's summary and message, otherwise the branch name is
used for the title.  Edit these fields as necessary  and click ``Create pull
request``.

.. note::

    Although these instructions seem to be the official pull request procedure
    on github's website, here are two alternative methods that are simpler.

    * If you navigate to your clone of salt,
      ``https://github.com/<my_account>/salt``, depending on how old your
      branch is or how recently you pushed updates on it, you may be presented
      with a button to create a pull request with your branch.

    * I find it easiest to edit the following URL:

      ``https://github.com/saltstack/salt/compare/|repo_primary_branch|...<my_account>:virt_ret``

---------
Resources
---------

GitHub offers many great tutorials on various aspects of the git- and
GitHub-centric development workflow:

https://help.github.com/

There are many topics covered by the Salt Developer documentation:

https://docs.saltstack.com/en/latest/topics/development/index.html

The contributing documentation presents more details on specific contributing
topics:

https://docs.saltstack.com/en/latest/topics/development/contributing.html
