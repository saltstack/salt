.. _pkging-introduction:

================
Onedir Packaging
================

Relenv onedir packaging
=======================

Starting in 3006, only onedir packaging will be available. The 3006 onedir packages
are built with the `relenv <https://github.com/saltstack/relative-environment-for-python>`_ tool.


Docker Containers
=================
The Salt Project uses docker containers to build our deb and rpm packages. If you are building your own packages you can use
the same containers we build with in the Github piplines. These containers are documented `here <https://github.com/saltstack/salt-ci-containers/tree/main/custom/packaging>`_.


How to build onedir only
========================

#. Install relenv:

    .. code-block:: bash

       pip install relenv

#. Fetch toolchain (Only required for linux OSs)

    .. code-block:: bash

       relenv toolchain fetch

#. Fetch Native Python Build:

    .. code-block:: bash

       relenv fetch --python=<python-version>

#. Create relenv environment:

    .. code-block:: bash

       relenv create --python=<python-version> <relenv-package-path>

#. Add Salt into onedir.

    .. code-block:: bash

       <relenv-package-path>/bin/pip install /path/to/salt


How to build rpm packages
=========================

#. Ensure you are in the current Salt cloned git repo:

    .. code-block:: bash

       cd <path-to-salt-repo>

#. Install the dependencies:

    .. code-block:: bash

       yum -y install python3 python3-pip openssl git rpmdevtools rpmlint systemd-units libxcrypt-compat git gnupg2 jq createrepo rpm-sign rustc cargo epel-release
       yum -y install patchelf
       pip install awscli

    .. code-block:: bash

       pip install -r requirements/static/ci/py{python_version}/tools.lock

#. (Optional) To build a specific Salt version, you will need to install tools and changelog dependencies:


    .. code-block:: bash

       pip install -r requirements/static/ci/py{python_version}/changelog.lock

#. (Optional) To build a specific Salt version, run tools and set Salt version:

    .. code-block:: bash

       tools changelog update-rpm <salt-version>

#. Build the RPM:

    Only the arch argument is required, the rest are optional.

    .. code-block:: bash

       tools pkg build rpm --relenv-version <relenv-version> --python-version <python-version> --arch <arch>


How to build deb packages
=========================

#. Ensure you are in the current Salt cloned git repo.:

    .. code-block:: bash

       cd <path-to-salt-repo>

#. Install the dependencies:

    .. code-block:: bash

       apt install -y apt-utils gnupg jq awscli python3 python3-venv python3-pip build-essential devscripts debhelper bash-completion git patchelf rustc

    .. code-block:: bash

       pip install -r requirements/static/ci/py{python_version}/tools.lock

#. (Optional) To build a specific Salt version, you will need to install changelog dependencies:

    .. code-block:: bash

       pip install -r requirements/static/ci/py{python_version}/changelog.lock

#. (Optional) To build a specific Salt version, run tools and set Salt version:

    .. code-block:: bash

       tools changelog update-deb <salt-version>


#. Build the deb package:

    Only the arch argument is required, the rest are optional.

    .. code-block:: bash

       tools pkg build deb --relenv-version <relenv-version> --python-version <python-version> --arch <arch>


How to build MacOS packages
===========================

#. Ensure you are in the current Salt cloned git repo.:

    .. code-block:: bash

       cd <path-to-salt-repo>

#. Install the dependencies:

    .. code-block:: bash

       pip install -r requirements/static/ci/py{python_version}/tools.lock

#. Build the MacOS package:

    Only the salt-version argument is required, the rest are optional.
    Do note that you will not be able to sign the packages when building them.

    .. code-block:: bash

       tools pkg build macos --salt-version <salt-version>


How to build Windows packages
=============================

#. Ensure you are in the current Salt cloned git repo.:

    .. code-block:: bash

       cd <path-to-salt-repo>

#. Install the dependencies:

    .. code-block:: bash

       pip install -r requirements/static/ci/py{python_version}/tools.lock

#. Build the MacOS package:

    Only the arch and salt-version arguments are required, the rest are optional.
    Do note that you will not be able to sign the packages when building them.

    .. code-block:: bash

       tools pkg build windows --salt-version <salt-version> --arch <arch>


How to access python binary
===========================

The python library is available in the install directory of the onedir package. For example
on linux the default location would be ``/opt/saltstack/salt/bin/python3``.

.. _salt-pip-onedir:

Installing optional Python dependencies into a onedir
=====================================================

The onedir packages bundle a pinned Python interpreter and a vendored Salt
install. To add a runtime dependency that one of Salt's modules needs --
for example ``boto3`` for the AWS execution modules, ``pymysql`` for the
``mysql`` modules, or any pure-Python library called from a custom module --
use ``salt-pip`` rather than the system ``pip``:

.. code-block:: bash

    salt-pip install boto3
    salt-pip install --upgrade pymysql
    salt-pip list

``salt-pip`` is a thin wrapper around the onedir's bundled ``pip`` that
targets an ``extras-<py-major>.<py-minor>`` directory alongside the onedir
install root (default ``/opt/saltstack/salt/extras-3.N``). Packages installed
there are picked up by the onedir Python via a ``.pth`` file, survive
package upgrades, and are isolated from the system Python.

.. note::

    Using the system ``pip3 install salt-...`` against the onedir's Python is
    not supported. The bundled interpreter is built with ``relenv`` and its
    site-packages layout differs from a system Python install.

Relocating the extras directory
-------------------------------

To put the extras outside ``/opt/saltstack/salt`` (for example so it lives on
a separate volume, or so it is owned by an unprivileged user), set
``SALT_EXTRAS_DIR`` in ``/etc/default/salt-setup`` (deb) or
``/etc/sysconfig/salt-minion-setup`` (rpm) before installing the package:

.. code-block:: bash

    echo 'SALT_EXTRAS_DIR=/srv/salt-extras' >> /etc/default/salt-setup
    salt-pip install boto3

The package post-install scripts source the same file on upgrade and reset
ownership of ``SALT_EXTRAS_DIR`` to the package's runtime user, so packages
installed under it are not orphaned by an upgrade.

Running ``salt-pip`` as a non-root user
---------------------------------------

When the minion runs as a non-root user (see
:ref:`configuration-non-root-user`), ``salt-pip`` reads ``user`` from the
minion config and drops privileges to that account before invoking pip. The
target user must own the onedir's extras directory. If you set
``SALT_EXTRAS_DIR`` to a non-default path, make sure that path is writable
by the configured ``user``.

Installing Salt Extensions
==========================

A Salt Extension is a separately distributed package of execution modules,
state modules, runners, or other plugin types. Extensions ship as standard
Python wheels named ``saltext.<name>`` (for example ``saltext.vmware``,
``saltext.cloud_aws``).

Install them into a onedir with ``salt-pip``:

.. code-block:: bash

    salt-pip install saltext.vmware
    systemctl restart salt-minion

Verify the extension's modules loaded:

.. code-block:: bash

    salt-call --local sys.list_modules | grep -i vmware

Notes:

* Pin to a version that matches the Salt major you have installed; many
  extensions require a minimum Salt release.
* If the extension provides state modules, they appear under their own
  virtual name -- ``saltext.cloud_aws`` exposes ``boto3_ec2`` and similar.
  Use ``salt-call --local sys.list_state_modules`` to enumerate.
* For source installs of an extension during development, use ``salt-pip
  install -e /path/to/saltext-foo`` so the editable install lands in the
  onedir's extras directory.
* See :ref:`salt_extensions` for the policy on which modules ship as
  extensions versus core.

Testing the packages
====================

If you want to test your built packages, or any other collection of salt packages post 3006.0, follow :ref:`this guide <pkging-testing>`

.. toctree::

     testing
