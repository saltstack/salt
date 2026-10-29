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

Package Grain
=============
In the 3007.0 release a new package grain was added. This detects how Salt was installed using the `_pkg.txt`
in the root of the Salt repo. By default this is set to ``pip``, but it is set to ``onedir`` when ``tools pkg build salt-onedir``
is run in our pipelines when building our onedir packages. If you are building your own custom packages, please ensure you set
``_pkg.txt`` contents to be the type of package you are creating. The options are ``pip``, ``onedir`` or ``system``.


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

The :py:mod:`pip execution module and state <salt.modules.pip>` work the
same way. On a onedir minion, ``pip.install``/``pip.installed`` without
``bin_env``/``pip_bin`` also install into the extras directory above, not
the system Python. To target the system Python instead, pass ``bin_env``
with the system's pip path, for example ``bin_env: /usr/bin/pip3``.

You can point ``bin_env``/``pip_bin``, or ``salt-pip install
--target=...``, at the onedir's real site-packages instead of the extras
directory, but this is unsupported: site-packages is replaced on every
Salt upgrade, so anything installed there is lost.

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

Locking down salt-pip's network access and PYTHONPATH
-------------------------------------------------------

Five minion config options let an operator control this behavior
centrally, instead of relying on every ``salt-pip`` caller to pass the
right flags by hand:

- :conf_minion:`saltpip_use_pythonpath` (default ``False``) -- opt back
  into inheriting the calling process's ``PYTHONPATH`` instead of the
  isolated-by-default behavior described above.
- :conf_minion:`saltpip_no_deps`, :conf_minion:`saltpip_no_index`, and
  :conf_minion:`saltpip_disable_pip_version_check` (all default ``False``)
  -- force ``salt-pip`` to never resolve dependencies, never query an
  index, and never check for a newer pip release, respectively. Turning
  on all three guarantees ``salt-pip`` can only install packages already
  present locally (e.g. pushed to the minion ahead of time) and never
  reaches out to PyPI or any other index.
- :conf_minion:`saltpip_allow_find_links` (default ``True``) -- set to
  ``False`` to also strip any inherited ``PIP_FIND_LINKS``, closing the
  one network path ``saltpip_no_index`` deliberately leaves open (pip
  treats ``--find-links`` as independent of the index, by design, so
  ``saltpip_no_index`` alone doesn't cover it).

See :ref:`configuration-salt-minion` for the full description of each
option.

Patching a vulnerable bundled dependency (advanced, unsupported)
----------------------------------------------------------------

A security scan may flag a CVE in a Python package bundled in the onedir's
site-packages (for example ``aiohttp``) before an official Salt release
fixes it. This section is an unsupported stop-gap for that situation. See
:ref:`disclosure` for how Salt ships security fixes, and move to an
official release as soon as one is available.

.. warning::

    This installs directly into the onedir's real site-packages, using its
    bundled ``pip``. Unlike ``salt-pip``, it does not isolate
    ``PYTHONPATH``. A stray or inherited ``PYTHONPATH`` here creates the
    same risk described in `issue #70151
    <https://github.com/saltstack/salt/issues/70151>`_, with nothing to
    protect you. Always clear ``PYTHONPATH`` first.

#. Stop ``salt-minion``/``salt-master``. A running process won't pick up
   the patch until it restarts.
#. Find the fixed package version, and any closely coupled dependencies, in
   the ``requirements/static/pkg/py<major.minor>/<platform>.lock`` file
   from the Salt release that fixes the CVE. Match your onedir's Python
   version (``/opt/saltstack/salt/bin/python3 --version``) and platform.
   For ``aiohttp``, also check ``aiohappyeyeballs``, ``aiosignal``,
   ``frozenlist``, ``multidict``, ``propcache``, and ``yarl`` -- upgrading
   ``aiohttp`` alone can pull in an incompatible version of one of these.
#. Install the fixed versions with ``PYTHONPATH`` cleared, pinning each
   version instead of using ``--force-reinstall`` (which can uninstall a
   package from anywhere pip finds it on ``sys.path``, not just
   site-packages):

   .. code-block:: bash

       PYTHONPATH= /opt/saltstack/salt/bin/python3 -m pip install \
           "aiohttp==<fixed-version>" "multidict==<matching-version>" \
           "yarl==<matching-version>" "frozenlist==<matching-version>" \
           "aiosignal==<matching-version>" "aiohappyeyeballs==<matching-version>" \
           "propcache==<matching-version>"

#. Confirm the new version: ``/opt/saltstack/salt/bin/python3 -m pip show
   aiohttp``.
#. Restart ``salt-minion``/``salt-master``.

Keep in mind:

* Site-packages is replaced on every Salt upgrade. Reapply the patch after
  each upgrade until an official release includes the fix, then drop it.
* Mismatched dependency versions can cause new problems of their own.
* This is a temporary measure, not a long-term solution.

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
