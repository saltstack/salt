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
  http://rst.ninjs.org/.
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

Create a new `virtualenv`_::

    virtualenv /path/to/your/virtualenv

.. _`virtualenv`: http://pypi.python.org/pypi/virtualenv

On Arch Linux, where Python 3 is the default installation of Python, use the
``virtualenv2`` command instead of ``virtualenv``.

.. note:: Using your system Python modules in the virtualenv

    If you have the required python modules installed on your system already
    and would like to use them in the virtualenv rather than having pip
    download and compile new ones into this environment, run ``virtualenv``
    with the ``--system-site-packages`` option. If you do this, you can skip
    the pip command below that installs the dependencies (pyzmq, M2Crypto,
    etc.), assuming that the listed modules are all installed in your system
    PYTHONPATH at the time you create your virtualenv.

Activate the virtualenv::

    source /path/to/your/virtualenv/bin/activate

Install Salt (and dependencies) into the virtualenv::

    pip install pyzmq M2Crypto PyYAML pycrypto msgpack-python jinja2 psutil
    pip install -e ./salt       # the path to the salt git clone from above

.. note:: Installing M2Crypto

    You may need ``swig`` and ``libssl-dev`` to build M2Crypto. If you 
    encounter the error ``command 'swig' failed with exit status 1``
    while installing M2Crypto, try installing it with the following command::

        env SWIG_FEATURES="-cpperraswarn -includeall -D__`uname -m`__ -I/usr/include/openssl" pip install M2Crypto

    Debian and Ubuntu systems have modified openssl libraries and mandate that
    a patched version of M2Crypto be installed. This means that M2Crypto
    needs to be installed via apt:

        apt-get install python-m2crypto


.. note:: Important note for those developing using RedHat variants

    If you are developing on a RedHat variant, be advised that the package
    provider for newer Redhat-based systems (:doc:`yumpkg.py
    <../ref/modules/all/salt.modules.yumpkg>`) relies on RedHat's python
    interface for yum. The variants that use this module to provide package
    support include the following:

    * `RHEL`_ and `CentOS`_ releases 6 and later
    * `Fedora Linux`_ releases 11 and later
    * `Amazon Linux`_

    If you are developing using one of these releases, you will want to create
    your virtualenv using the ``--system-site-packages`` option so that these
    modules are available in the virtualenv.

.. _`RHEL`: https://www.redhat.com/products/enterprise-linux/
.. _`CentOS`: http://centos.org/
.. _`Fedora Linux`: http://fedoraproject.org/
.. _`Amazon Linux`: https://aws.amazon.com/amazon-linux-ami/


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
3.  Uncomment and change the ``pidfile: /var/run/salt-minion.pid`` value to
    point to ``/path/to/your/virtualenv/salt-minion.pid``.
4.  If you are also running a non-development version of Salt you will have to
    change the ``publish_port`` and ``ret_port`` values as well.

Edit the minion config file:

1.  Repeat the edits you made in the master config for the ``user`` and
    ``root_dir`` values as well as any port changes.
2.  Uncomment and change the ``pidfile: /var/run/salt-master.pid`` value to
    point to ``/path/to/your/virtualenv/salt-master.pid``.
3.  Uncomment and change the ``master: salt`` value to point at ``localhost``.
4.  Uncomment and change the ``id:`` value to something descriptive like
    "saltdev". This isn't strictly necessary but it will serve as a reminder of
    which Salt installation you are working with.

.. note:: Using `salt-call` with a :doc:`Standalone Minion </topics/tutorials/standalone_minion>`

    If you plan to run `salt-call` with this self-contained development
    environment in a masterless setup, you should invoke `salt-call` with
    ``-c /path/to/your/virtualenv/etc/salt`` so that salt can find the minion
    config file. Without the ``-c`` option, Salt finds its config files in
    `/etc/salt`.

Start the master and minion, accept the minon's key, and verify your local Salt
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

File descriptor limit
~~~~~~~~~~~~~~~~~~~~~

Check your file descriptor limit with::

    ulimit -n

If it is less than 2047, you should increase it with::

    ulimit -n 2047
    (or "limit descriptors 2047" for c-shell)


Running the tests
~~~~~~~~~~~~~~~~~

You will need ``mock`` to run the tests::

    pip install mock

If you are on Python < 2.7 then you will also need unittest2::

    pip install unittest2

Finally you use setup.py to run the tests with the following command::

    ./setup.py test

For greater control while running the tests, please try::

    ./tests/runtests.py -h
