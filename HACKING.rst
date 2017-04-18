Developing Salt
===============

If you want to help develop Salt there is a great need and your patches are
welcome!

To assist in Salt development, you can help in a number of ways.

Setting a GitHub pull request
-----------------------------

This is the preferred method for contributions, simply create a GitHub
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
  that runs for that piece. Find them in ``salt/modules/`` or ``salt/states/``.
- If you are developing using Arch Linux (or any other distribution for which
  Python 3 is the default Python installation), then ``sphinx-build`` may be
  named ``sphinx-build2`` instead. If this is the case, then you will need to
  run the following ``make`` command::

    make SPHINXBUILD=sphinx-build2 html

Installing Salt for development
-------------------------------

Clone the repository using::

    git clone https://github.com/saltstack/salt
    cd salt

.. note:: tags

    Just cloning the repository is enough to work with Salt and make
    contributions. However, you must fetch additional tags into your clone to
    have Salt report the correct version for itself. To do this, fetch the tags
    with the command::

        git fetch --tags

Preparing your system
~~~~~~~~~~~~~~~~~~~~~

In order to install Salt's requirements, you'll need a system with a compiler
and Python's development libraries.

Debian-based systems
````````````````````

On Debian and derivative systems such as Ubuntu, system requirements can be
installed by running::

    apt-get install -y build-essential libssl-dev python-dev python-m2crypto \
      python-pip python-virtualenv swig virtualenvwrapper

RedHat-based systems
````````````````````

If you are developing using one of these releases, you will want to create your
virtualenv using the ``--system-site-packages`` option so that these modules
are available in the virtualenv.

M2Crypto also supplies a fedora_setup.sh script you may use as well if you get
the following error::

    This openssl-devel package does not work your architecture?. Use the -cpperraswarn option to continue swig processing.

You can use it doing the following::

    cd <path-to-your-venv>/build/M2Crypto
    chmod u+x fedora_setup.sh
    ./fedora_setup.sh build
    ./fedora_setup.sh install


Installing dependencies on macOS
````````````````````````````````

One simple way to get all needed dependencies on macOS is to use homebrew,
and install the following packages::

    brew install swig
    brew install zmq

Afterward the pip commands should run without a hitch. Also be sure to set
max_open_files to 2048 (see below).

Create a virtual environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create a new `virtualenv`_::

    virtualenv /path/to/your/virtualenv

.. _`virtualenv`: http://pypi.python.org/pypi/virtualenv

On Arch Linux, where Python 3 is the default installation of Python, use the
``virtualenv2`` command instead of ``virtualenv``.

Debian, Ubuntu, and the RedHat systems mentioned above, you should use
``--system-site-packages`` when creating the virtualenv, to pull in the
M2Crypto installed using apt::

    virtualenv --system-site-packages /path/to/your/virtualenv

On Gentoo systems you should use ``--system-site-packages`` when creating
the virtualenv to enable pkg and portage_config functionality as the
portage package is not available via pip

.. note:: Using your system Python modules in the virtualenv

    If you have the required python modules installed on your system already
    and would like to use them in the virtualenv rather than having pip
    download and compile new ones into this environment, run ``virtualenv``
    with the ``--system-site-packages`` option. If you do this, you can skip
    the pip command below that installs the dependencies (pyzmq, M2Crypto,
    etc.), assuming that the listed modules are all installed in your system
    PYTHONPATH at the time you create your virtualenv.

Configure your virtual environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Activate the virtualenv::

    source /path/to/your/virtualenv/bin/activate

Install Salt (and dependencies) into the virtualenv.

ZeroMQ Transport:

.. code-block:: bash

    pip install -r requirements/zeromq.txt
    pip install psutil
    pip install -e .

.. note:: Installing M2Crypto

    You may need ``swig`` and ``libssl-dev`` to build M2Crypto. If you
    encounter the error ``command 'swig' failed with exit status 1``
    while installing M2Crypto, try installing it with the following command::

        env SWIG_FEATURES="-cpperraswarn -includeall -D__`uname -m`__ -I/usr/include/openssl" pip install M2Crypto


RAET Transport:

.. code-block:: bash

    pip install -r requirements/raet.txt
    pip install psutil
    pip install -e .


Running a self-contained development version
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

During development it is easiest to be able to run the Salt master and minion
that are installed in the virtualenv you created above, and also to have all
the configuration, log, and cache files contained in the virtualenv as well.

Copy the master and minion config files into your virtualenv::

    mkdir -p /path/to/your/virtualenv/etc/salt
    cp ./salt/conf/master /path/to/your/virtualenv/etc/salt/master
    cp ./salt/conf/minion /path/to/your/virtualenv/etc/salt/minion

Edit the master config file:

1.  Uncomment and change the ``user: root`` value to your own user.
2.  Uncomment and change the ``root_dir: /`` value to point to
    ``/path/to/your/virtualenv``.
3.  If you are running version 0.11.1 or older, uncomment and change the
    ``pidfile: /var/run/salt-master.pid`` value to point to
    ``/path/to/your/virtualenv/salt-master.pid``.
4.  If you are also running a non-development version of Salt you will have to
    change the ``publish_port`` and ``ret_port`` values as well.
5. On xxxOS X also set max_open_files to 2048.

Edit the minion config file:

1.  Repeat the edits you made in the master config for the ``user`` and
    ``root_dir`` values as well as any port changes.
2.  If you are running version 0.11.1 or older, uncomment and change the
    ``pidfile: /var/run/salt-minion.pid`` value to point to
    ``/path/to/your/virtualenv/salt-minion.pid``.
3.  Uncomment and change the ``master: salt`` value to point at ``localhost``.
4.  Uncomment and change the ``id:`` value to something descriptive like
    "saltdev". This isn't strictly necessary but it will serve as a reminder of
    which Salt installation you are working with.
5.  If you changed the ``ret_port`` value in the master config because you are
    also running a non-development version of Salt, then you will have to
    change the ``master_port`` value in the minion config to match.

.. note:: Using `salt-call` with a :ref:`Standalone Minion <tutorial-standalone-minion>`

    If you plan to run `salt-call` with this self-contained development
    environment in a masterless setup, you should invoke `salt-call` with
    ``-c /path/to/your/virtualenv/etc/salt`` so that salt can find the minion
    config file. Without the ``-c`` option, Salt finds its config files in
    `/etc/salt`.

Start the master and minion, accept the minion's key, and verify your local Salt
installation is working::

    cd /path/to/your/virtualenv
    salt-master -c ./etc/salt -d
    salt-minion -c ./etc/salt -d
    salt-key -c ./etc/salt -L
    salt-key -c ./etc/salt -A
    salt -c ./etc/salt '*' test.ping

Running the master and minion in debug mode can be helpful when developing. To
do this, add ``-l debug`` to the calls to ``salt-master`` and ``salt-minion``.
If you would like to log to the console instead of to the log file, remove the
``-d``.

Once the minion starts, you may see an error like the following::

    zmq.core.error.ZMQError: ipc path "/path/to/your/virtualenv/var/run/salt/minion/minion_event_7824dcbcfd7a8f6755939af70b96249f_pub.ipc" is longer than 107 characters (sizeof(sockaddr_un.sun_path)).

This means that the path to the socket the minion is using is too long. This is
a system limitation, so the only workaround is to reduce the length of this
path. This can be done in a couple different ways:

1.  Create your virtualenv in a path that is short enough.
2.  Edit the :conf_minion:`sock_dir` minion config variable and reduce its
    length. Remember that this path is relative to the value you set in
    :conf_minion:`root_dir`.

``NOTE:`` The socket path is limited to 107 characters on Solaris and Linux,
and 103 characters on BSD-based systems.
File descriptor limit
~~~~~~~~~~~~~~~~~~~~~

Check your file descriptor limit with::

    ulimit -n

If it is less than 2047, you should increase it with::

    ulimit -n 2047
    (or "limit descriptors 2047" for c-shell)


Running the tests
~~~~~~~~~~~~~~~~~

For running tests, you'll also need to install ``requirements/dev_python2x.txt``::

    pip install -r requirements/dev_python2x.txt

Finally you use setup.py to run the tests with the following command::

    ./setup.py test

For greater control while running the tests, please try::

	./tests/runtests.py -h
