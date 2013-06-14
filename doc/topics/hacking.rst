Developing Salt
===============

There is a great need for contributions to salt and patches are welcome! The goal 
here is to make contributions clear, make sure there is a trail for where the code 
has come from, and most importantly, to give credit where credit is due!

There are a number of ways to contribute to salt development.


Sending a Github pull request
-----------------------------

This is the preferred method for contributions. Simply create a Github
fork, commit changes to the fork, and then open up a pull request.

The following is an example (from `Open Comparison Contributing Docs`_ ) 
of an efficient workflow for forking, cloning, branching, committing, and 
sending a pull request for a github repository.

First, make a local clone of your github fork of the salt github repo and make
edits and changes locally.

Then, create a new branch on your clone by entering the following commands::

    git checkout -b fixed-broken-thing

    Switched to a new branch 'fixed-broken-thing'

Choose a name for your branch that describes its purpose.  

Now commit your changes to this new branch with the following command::

    #add and commit all changes at once
    git commit -a -m 'description of my fixes for the broken thing'

And then push your locally committed changes back up to GitHub::

    git push --set-upstream origin fixed-broken-thing
    
Now go look at your fork of the salt repo on the GitHub website. The new 
branch will now be listed under the "Source" tab where it says "Switch Branches".
Select the new branch from this list, and then click the "Pull request" button.

Put in a descriptive comment, and include links to any project issues related to the pull request.

The repo managers will be notified of your pull request and it will
be reviewed. If a reviewer asks for changes, just make the changes locally in the 
same local feature branch, push them to GitHub, then add a comment to the 
discussion section of the pull request. 

.. note:: Travis-CI

    To make reviewing pull requests easier for the maintainers, please enable Travis-CI on 
    the fork. Salt is already configured, so simply follow the first 
    2 steps on the Travis-CI `Getting Started Doc`_.

.. _`Getting Started Doc`: http://about.travis-ci.org/docs/user/getting-started

Keeping Salt Forks in Sync
--------------------------

Salt is advancing quickly. It is therefore critical to pull upstream changes from master into forks on a regular basis. Nothing is worse than putting in a days of hard work into a pull request only to have it rejected because it has diverged too far from master. 

To pull in upstream changes::

    # For ssh github
    git remote add upstream git@github.com:saltstack/salt.git
    git fetch upstream

    # For https github
    git remote add upstream https://github.com/saltstack/salt.git
    git fetch upstream


To check the log to be sure that you actually want the changes, run this before merging::

    git log upstream/develop

Then to accept the changes and merge into the current branch::

    git merge upstream/develop

For more info, see `Github Fork a Repo Guide`_ or `Open Comparison Contributing Docs`_

.. _`Github Fork a Repo Guide`: http://help.github.com/fork-a-repo/
.. _`Open Comparison Contributing Docs`: http://opencomparison.readthedocs.org/en/latest/contributing.html

Posting patches to the mailing list
-----------------------------------

Patches will also be accepted by email. Format patches using `git format-patch`_
and send them to the Salt users mailing list. The contributor will then get credit 
for the patch, and the Salt community will have an archive of the patch and a place for discussion.

.. _`git format-patch`: http://www.kernel.org/pub/software/scm/git/docs/git-format-patch.html

Installing Salt for development
-------------------------------

Clone the repository using::

    git clone https://github.com/saltstack/salt

.. note:: tags

    Just cloning the repository is enough to work with Salt and make
    contributions. However, fetching additional tags from git is required to
    have Salt report the correct version for itself. To do this, first
    add the git repository as an upstream source::

        git remote add upstream http://github.com/saltstack/salt

    Fetching tags is done with the git 'fetch' utility::

        git fetch --tags upstream

Create a new `virtualenv`_::

    virtualenv /path/to/your/virtualenv

.. _`virtualenv`: http://pypi.python.org/pypi/virtualenv

On Arch Linux, where Python 3 is the default installation of Python, use the
``virtualenv2`` command instead of ``virtualenv``.

.. note:: Using system Python modules in the virtualenv

    To use already-installed python modules in virtualenv (instead of having pip
    download and compile new ones), run ``virtualenv --system-site-packages``
    Using this method eliminates the requirement to install the salt dependencies
    again, although it does assume that the listed modules are all installed in the
    system PYTHONPATH at the time of virtualenv creation.

Activate the virtualenv::

    source /path/to/your/virtualenv/bin/activate

Install Salt (and dependencies) into the virtualenv::

    pip install M2Crypto    # Don't install on Debian/Ubuntu (see below)
    pip install pyzmq PyYAML pycrypto msgpack-python jinja2 psutil
    pip install -e ./salt   # the path to the salt git clone from above

.. note:: Installing M2Crypto

    ``swig`` and ``libssl-dev`` are required to build M2Crypto. To fix
    the error ``command 'swig' failed with exit status 1`` while installing M2Crypto, 
    try installing it with the following command::

        env SWIG_FEATURES="-cpperraswarn -includeall -D__`uname -m`__ -I/usr/include/openssl" pip install M2Crypto

    Debian and Ubuntu systems have modified openssl libraries and mandate that
    a patched version of M2Crypto be installed. This means that M2Crypto
    needs to be installed via apt::

        apt-get install python-m2crypto

    This also means that pulling in the M2Crypto installed using apt requires using
    ``--system-site-packages`` when creating the virtualenv.

.. note:: Installing psutil

    Python header files are required to build this module, otherwise the pip
    install will fail. If your distribution separates binaries and headers into
    separate packages, make sure that you have the headers installed. In most
    Linux distributions which split the headers into their own package, this
    can be done by installing the ``python-dev`` or ``python-devel`` package.
    For other platforms, the package will likely be similarly named.

.. note:: Important note for those developing using RedHat variants

    For developers using a RedHat variant, be advised that the package
    provider for newer Redhat-based systems (:doc:`yumpkg.py
    <../ref/modules/all/salt.modules.yumpkg>`) relies on RedHat's python
    interface for yum. The variants that use this module to provide package
    support include the following:

    * `RHEL`_ and `CentOS`_ releases 6 and later
    * `Fedora Linux`_ releases 11 and later
    * `Amazon Linux`_

    Developers using one of these systems should create the salt virtualenv using the 
    ``--system-site-packages`` option to ensure that the correct modules are available.

.. _`RHEL`: https://www.redhat.com/products/enterprise-linux/
.. _`CentOS`: http://centos.org/
.. _`Fedora Linux`: http://fedoraproject.org/
.. _`Amazon Linux`: https://aws.amazon.com/amazon-linux-ami/

.. note:: Installing dependencies on OS X.

    You can install needed dependencies on OS X using homebrew or macports.
    See :doc:`OS X Installation </topics/installation/osx>`

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

.. note:: Using `salt-call` with a :doc:`Standalone Minion </topics/tutorials/standalone_minion>`

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

This means the the path to the socket the minion is using is too long. This is
a system limitation, so the only workaround is to reduce the length of this
path. This can be done in a couple different ways:

1.  Create your virtualenv in a path that is short enough.
2.  Edit the :conf_minion:`sock_dir` minion config variable and reduce its
    length. Remember that this path is relative to the value you set in
    :conf_minion:`root_dir`.

``NOTE:`` The socket path is limited to 107 characters on Solaris and Linux,
and 103 characters on BSD-based systems.

.. note:: File descriptor limits

    Ensure that the system open file limit is raised to at least 2047::

        # check your current limit
        ulimit -n

        # raise the limit. persists only until reboot
        # use 'limit descriptors 2047' for c-shell
        ulimit -n 2047

    To set file descriptors on OSX, refer to the :doc:`OS X Installation </topics/installation/osx>` instructions.


Using easy_install to Install Salt
----------------------------------

If you are installing using ``easy_install``, you will need to define a
:strong:`USE_SETUPTOOLS` environment variable, otherwise dependencies will not
be installed.

    $ USE_SETUPTOOLS=1 easy_install salt

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

Editing and previewing the documention
--------------------------------------

You need ``sphinx-build`` command to build the docs. In Debian/Ubuntu this is
provided in the ``python-sphinx`` package. Sphinx can also be installed
to a virtualenv using pip::

    pip install Sphinx

Change to salt documention directory, then::

    cd doc; make html

- This will build the HTML docs. Run ``make`` without any arguments to see the
  available make targets, which include :strong:`html`, :strong:`man`, and
  :strong:`text`.
- The docs then are built within the :strong:`docs/_build/` folder. To update
  the docs after making changes, run ``make`` again.
- The docs use `reStructuredText <http://sphinx-doc.org/rest.html>`_ for markup.
  See a live demo at http://rst.ninjs.org/.
- The help information on each module or state is culled from the python code
  that runs for that piece. Find them in ``salt/modules/`` or ``salt/states/``.

- To build the docs on Arch Linux, the :strong:`python2-sphinx` package is
  required. Additionally, it is necessary to tell :strong:`make` where to find
  the proper :strong:`sphinx-build` binary, like so::

    make SPHINXBUILD=sphinx-build2 html

- To build the docs on RHEL/CentOS 6, the :strong:`python-sphinx10` package
  must be installed from EPEL, and the following make command must be used::

    make SPHINXBUILD=sphinx-1.0-build html
