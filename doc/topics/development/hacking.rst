.. _installing-for-development:

Installing Salt for development
===============================

Clone the repository using:

.. code-block:: bash

    git clone https://github.com/saltstack/salt

.. note:: tags

    Just cloning the repository is enough to work with Salt and make
    contributions. However, fetching additional tags from git is required to
    have Salt report the correct version for itself. To do this, first
    add the git repository as an upstream source:

    .. code-block:: bash

        git remote add upstream https://github.com/saltstack/salt

    Fetching tags is done with the git 'fetch' utility:

    .. code-block:: bash

        git fetch --tags upstream

Create a new `virtualenv`_:

.. code-block:: bash

    virtualenv /path/to/your/virtualenv

.. _`virtualenv`: https://pypi.org/project/virtualenv/

Avoid making your :ref:`virtualenv path too long <too_long_socket_path>`.

On Arch Linux, where Python 3 is the default installation of Python, use
the ``virtualenv2`` command instead of ``virtualenv``.

On Gentoo you must use ``--system-site-packages`` to enable pkg and portage_config
functionality

.. note:: Using system Python modules in the virtualenv

    To use already-installed python modules in virtualenv (instead of having pip
    download and compile new ones), run ``virtualenv --system-site-packages``
    Using this method eliminates the requirement to install the salt dependencies
    again, although it does assume that the listed modules are all installed in the
    system PYTHONPATH at the time of virtualenv creation.

.. note:: Python development package

    Be sure to install python devel package in order to install required Python
    modules. In Debian/Ubuntu run ``sudo apt-get install -y python-dev``. In RedHat
    based system install ``python-devel``

Activate the virtualenv:

.. code-block:: bash

    source /path/to/your/virtualenv/bin/activate

Install Salt (and dependencies) into the virtualenv:

.. code-block:: bash

    pip install pyzmq PyYAML pycrypto msgpack jinja2 psutil futures tornado
    pip install -e ./salt   # the path to the salt git clone from above

.. note:: Installing psutil

    Python header files are required to build this module, otherwise the pip
    install will fail. If your distribution separates binaries and headers into
    separate packages, make sure that you have the headers installed. In most
    Linux distributions which split the headers into their own package, this
    can be done by installing the ``python-dev`` or ``python-devel`` package.
    For other platforms, the package will likely be similarly named.

.. _`RHEL`: https://www.redhat.com/products/enterprise-linux/
.. _`CentOS`: http://centos.org/
.. _`Fedora Linux`: http://fedoraproject.org/
.. _`Amazon Linux`: https://aws.amazon.com/amazon-linux-ami/

.. note:: Installing dependencies on macOS.

    You can install needed dependencies on macOS using homebrew or macports.
    See the
    `Salt install guide <https://docs.saltproject.io/salt/install-guide/en/latest/>`_
    for more information.

.. warning:: Installing on RedHat-based Distros

    If installing from pip (or from source using ``setup.py install``), be
    advised that the ``yum-utils`` package is needed for Salt to manage
    packages on RedHat-based systems.

Running a self-contained development version
--------------------------------------------

During development it is easiest to be able to run the Salt master and minion
that are installed in the virtualenv you created above, and also to have all
the configuration, log, and cache files contained in the virtualenv as well.

The ``/path/to/your/virtualenv`` referenced multiple times below is also
available in the variable ``$VIRTUAL_ENV`` once the virtual environment is
activated.

Copy the master and minion config files into your virtualenv:

.. code-block:: bash

    mkdir -p /path/to/your/virtualenv/etc/salt/pki/{master,minion}
    cp ./salt/conf/master ./salt/conf/minion /path/to/your/virtualenv/etc/salt/

Edit the master config file:

1.  Uncomment and change the ``user: root`` value to your own user.
2.  Uncomment and change the ``root_dir: /`` value to point to
    ``/path/to/your/virtualenv``.
3.  Uncomment and change the ``pki_dir: /etc/salt/pki/master`` value to point to
    ``/path/to/your/virtualenv/etc/salt/pki/master``
4.  If you are running version 0.11.1 or older, uncomment, and change the
    ``pidfile: /var/run/salt-master.pid`` value to point to
    ``/path/to/your/virtualenv/salt-master.pid``.
5.  If you are also running a non-development version of Salt you will have to
    change the ``publish_port`` and ``ret_port`` values as well.

Edit the minion config file:

1.  Repeat the edits you made in the master config for the ``user`` and
    ``root_dir`` values as well as any port changes.
2.  Uncomment and change the ``pki_dir: /etc/salt/pki/minion`` value to point to
    ``/path/to/your/virtualenv/etc/salt/pki/minion``
3.  If you are running version 0.11.1 or older, uncomment, and change the
    ``pidfile: /var/run/salt-minion.pid`` value to point to
    ``/path/to/your/virtualenv/salt-minion.pid``.
4.  Uncomment and change the ``master: salt`` value to point at ``localhost``.
5.  Uncomment and change the ``id:`` value to something descriptive like
    "saltdev". This isn't strictly necessary but it will serve as a reminder of
    which Salt installation you are working with.
6.  If you changed the ``ret_port`` value in the master config because you are
    also running a non-development version of Salt, then you will have to
    change the ``master_port`` value in the minion config to match.

.. note:: Using `salt-call` with a :ref:`Standalone Minion <tutorial-standalone-minion>`

    If you plan to run `salt-call` with this self-contained development
    environment in a masterless setup, you should invoke `salt-call` with
    ``-c /path/to/your/virtualenv/etc/salt`` so that salt can find the minion
    config file. Without the ``-c`` option, Salt finds its config files in
    `/etc/salt`.

Start the master and minion, accept the minion's key, and verify your local Salt
installation is working:

.. code-block:: bash

    cd /path/to/your/virtualenv
    salt-master -c ./etc/salt -d
    salt-minion -c ./etc/salt -d
    salt-key -c ./etc/salt -L
    salt-key -c ./etc/salt -A
    salt -c ./etc/salt '*' test.version

Running the master and minion in debug mode can be helpful when developing. To
do this, add ``-l debug`` to the calls to ``salt-master`` and ``salt-minion``.
If you would like to log to the console instead of to the log file, remove the
``-d``.

.. _too_long_socket_path:
.. note:: Too long socket path?

    Once the minion starts, you may see an error like the following:

    .. code-block:: console

        zmq.core.error.ZMQError: ipc path "/path/to/your/virtualenv/
        var/run/salt/minion/minion_event_7824dcbcfd7a8f6755939af70b96249f_pub.ipc"
        is longer than 107 characters (sizeof(sockaddr_un.sun_path)).

    This means that the path to the socket the minion is using is too long. This is
    a system limitation, so the only workaround is to reduce the length of this
    path. This can be done in a couple different ways:

    1.  Create your virtualenv in a path that is short enough.
    2.  Edit the :conf_minion:`sock_dir` minion config variable and reduce its
        length. Remember that this path is relative to the value you set in
        :conf_minion:`root_dir`.

    ``NOTE:`` The socket path is limited to 107 characters on Solaris and Linux,
    and 103 characters on BSD-based systems.

.. note:: File descriptor limits

    Ensure that the system open file limit is raised to at least 2047:

    .. code-block:: bash

        # check your current limit
        ulimit -n

        # raise the limit. persists only until reboot
        # use 'limit descriptors 2047' for c-shell
        ulimit -n 2047

    To set file descriptors on macOS, see the
    `Salt install guide <https://docs.saltproject.io/salt/install-guide/en/latest/>`_
    instructions for macOS.


Changing Default Paths
~~~~~~~~~~~~~~~~~~~~~~

Instead of updating your configuration files to point to the new root directory
and having to pass the new configuration directory path to all of Salt's CLI
tools, you can explicitly tweak the default system paths that Salt expects:

.. code-block:: bash

    GENERATE_SALT_SYSPATHS=1 pip install --global-option='--salt-root-dir=/path/to/your/virtualenv/' \
        -e ./salt   # the path to the salt git clone from above


You can now call all of Salt's CLI tools without explicitly passing the configuration directory.

Additional Options
..................

If you want to distribute your virtualenv, you probably don't want to include
Salt's clone ``.git/`` directory, and, without it, Salt won't report the
accurate version. You can tell ``setup.py`` to generate the hardcoded version
information which is distributable:

.. code-block:: bash

    GENERATE_SALT_SYSPATHS=1 WRITE_SALT_VERSION=1 pip install --global-option='--salt-root-dir=/path/to/your/virtualenv/' \
        -e ./salt   # the path to the salt git clone from above


Instead of passing those two environmental variables, you can just pass a
single one which will trigger the other two:

.. code-block:: bash

    MIMIC_SALT_INSTALL=1 pip install --global-option='--salt-root-dir=/path/to/your/virtualenv/' \
        -e ./salt   # the path to the salt git clone from above


This last one will grant you an editable salt installation with hardcoded
system paths and version information.


Installing Salt from the Python Package Index
---------------------------------------------

If you are installing using ``easy_install``, you will need to define a
:strong:`USE_SETUPTOOLS` environment variable, otherwise dependencies will not
be installed:

.. code-block:: bash

    USE_SETUPTOOLS=1 easy_install salt


Editing and previewing the documentation
----------------------------------------

You need ``sphinx-build`` command to build the docs. In Debian/Ubuntu this is
provided in the ``python-sphinx`` package. Sphinx can also be installed
to a virtualenv using pip:

.. code-block:: bash

    pip install Sphinx==1.3.1

Change to salt documentation directory, then:

.. code-block:: bash

    cd doc; make html

- This will build the HTML docs. Run ``make`` without any arguments to see the
  available make targets, which include :strong:`html`, :strong:`man`, and
  :strong:`text`.
- The docs then are built within the :strong:`docs/_build/` folder. To update
  the docs after making changes, run ``make`` again.
- The docs use `reStructuredText
  <https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html>`_
  for markup.
  See a live demo at http://rst.ninjs.org/.
- The help information on each module or state is culled from the python code
  that runs for that piece. Find them in ``salt/modules/`` or ``salt/states/``.

- To build the docs on Arch Linux, the :strong:`python2-sphinx` package is
  required. Additionally, it is necessary to tell :strong:`make` where to find
  the proper :strong:`sphinx-build` binary, like so:

.. code-block:: bash

    make SPHINXBUILD=sphinx-build2 html

- To build the docs on RHEL/CentOS 6, the :strong:`python-sphinx10` package
  must be installed from EPEL, and the following make command must be used:

.. code-block:: bash

    make SPHINXBUILD=sphinx-build html

Once you've updated the documentation, you can run the following command to
launch a simple Python HTTP server to see your changes:

.. code-block:: bash

    cd _build/html; python -m SimpleHTTPServer

Running unit and integration tests
----------------------------------

Run the test suite with following command:

.. code-block:: bash

    ./setup.py test

See :ref:`here <salt-test-suite>` for more information regarding the test suite.

Issue and Pull Request Labeling System
--------------------------------------

SaltStack uses several labeling schemes to help facilitate code contributions
and bug resolution. See the :ref:`Labels and Milestones
<labels-and-milestones>` documentation for more information.
