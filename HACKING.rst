Developing Salt
===============

If you want to help develop Salt there is a great need and your patches are
welcome!

To assist in Salt development, you can help in a number of ways.

Setting a Github pull request
-----------------------------

This is the preferred method for contributions, simply create a Github
fork, commit your changes to the fork, and then open up a pull request.

Posting patches to the mailing list
-----------------------------------

If you have a patch for Salt, please format it via :command:`git format-patch`
and send it to the Salt users mailing list. This allows the patch to give you
the contributor the credit for your patch, and gives the Salt community an
archive of the patch and a place for discussion.

Contributions Welcome!
----------------------

The goal here it to make contributions clear, make sure there is a trail for
where the code has come from, but most importantly, to give credit where credit
is due!

The `Open Comparison Contributing Docs`__ explains the workflow for forking,
cloning, branching, committing, and sending a pull request for the git
repository.

``git pull upstream develop`` is a shorter way to update your local repository
to the latest version.

.. __: http://opencomparison.readthedocs.org/en/latest/contributing.html

Editing and Previewing the Docs
-------------------------------
You need ``sphinx-build`` to build the docs. In Debian/ubuntu, this is provided
in the ``python-sphinx`` package.

Then::

    cd doc; make html

- The docs then are built in the ``docs/_build/html/`` folder. If you make
  changes and want to see the results, ``make html`` again.
- The docs use ``reStructuredText`` for markup. See a live demo at
  http://rst.ninjs.org/
- The help information on each module or state is culled from the python code
  that runs for that piece. Find them in ``salt/modules/`` or ``salt/states/``


Getting the tests running
-------------------------

Clone the repository using::

    git clone https://github.com/saltstack/salt

File descriptor limit
~~~~~~~~~~~~~~~~~~~~~

Check your file descriptor limit with::

    ulimit -n

If it is less than 1024, you should increase it with::

    ulimit -n 1024

Requirements
~~~~~~~~~~~~

First you'll want to create a `virtualenv`_. Once you've done that
install the requirements like so::

    pip install -r requirements.txt

You'll also need ``mock`` to run the tests::

    pip install mock

If you are on Python < 2.7 then you'll also need::

    pip install unittest2

.. _`virtualenv`: http://pypi.python.org/pypi/virtualenv

Run them
~~~~~~~~

Finally you use setup.py to run the tests with the following command::

    ./setup.py test
