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

The goal here is to make contributions clear, make sure there is a trail for
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
You need ``sphinx-build`` to build the docs. In Debian/Ubuntu this is provided
in the ``python-sphinx`` package.

Then::

    cd doc; make html

- The docs then are built in the ``docs/_build/html/`` folder. If you make
  changes and want to see the results, ``make html`` again.
- The docs use ``reStructuredText`` for markup. See a live demo at
  http://rst.ninjs.org/
- The help information on each module or state is culled from the python code
  that runs for that piece. Find them in ``salt/modules/`` or ``salt/states/``

Installing Salt for development
-------------------------------

Clone the repository using::

    git clone https://github.com/saltstack/salt

Create a new `virtualenv`_::

    virtualenv /path/to/your/virtualenv

.. _`virtualenv`: http://pypi.python.org/pypi/virtualenv

Activate the virtualenv::

    source /path/to/your/virtualenv/bin/activate

Install Salt (and dependencies) into the virtualenv::

    pip install -e ./salt       # the path to the salt git clone from above

.. note:: Installing M2Crypto

    If you and encounter the error ``command 'swig' failed with exit status 1``
    while installing M2Crypto, try installing it with the following command::

        env SWIG_FEATURES="-cpperraswarn -includeall -D__`uname -m`__ -I/usr/include/openssl" pip install M2Crypto

Running a self-contained development version
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

During development it is easiest to be able to run the Salt master and minion
that are installed in the virtualenv you created above, and also to have all
the configuration, log, and cache files contained in the virtualenv as well.

Copy the master and minion config files into your virtualenv::

    mkdir -p /path/to/your/virtualenv/etc/salt
    cp ./salt/conf/master.template /path/to/your/virtualenv/etc/salt/master
    cp ./salt/conf/minion.template /path/to/your/virtualenv/etc/salt/minion

Edit the master config file:

1.  Uncomment and change the ``user: root`` value to your own user.
2.  Uncomment and change the ``root_dir: /`` value to point to
    ``/path/to/your/virtualenv``.
3.  If you are also running a non-development version of Salt you will have to
    change the ``publish_port`` and ``ret_port`` values as well.

Edit the minion config file:

1.  Repeat the edits you made in the master config for the ``user`` and
    ``root_dir`` values as well as any port changes.
2.  Uncomment and change the ``master: salt`` value to point at ``localhost``.
3.  Uncomment and change the ``id:`` value to something descriptive like
    "saltdev". This isn't strictly necessary but it will serve as a reminder of
    which Salt installation you are working with.

Start the master and minion, accept the minon's key, and verify your local Salt
installation is working::

    salt-master -c ./etc/salt/master -d
    salt-minion -c ./etc/salt/minion -d
    salt-key -c ./etc/salt/master -L
    salt-key -c ./etc/salt/master -A
    salt -c ./etc/salt/master '*' test.ping

File descriptor limit
~~~~~~~~~~~~~~~~~~~~~

Check your file descriptor limit with::

    ulimit -n

If it is less than 1024, you should increase it with::

    ulimit -n 1024

Running the tests
~~~~~~~~~~~~~~~~~

You will need ``mock`` to run the tests::

    pip install mock

If you are on Python < 2.7 then you will also need unittest2::

    pip install unittest2

Finally you use setup.py to run the tests with the following command::

    ./setup.py test
