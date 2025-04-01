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

       pip install -r requirements/static/ci/py{python_version}/tools.txt

#. (Optional) To build a specific Salt version, you will need to install tools and changelog dependencies:


    .. code-block:: bash

       pip install -r requirements/static/ci/py{python_version}/changelog.txt

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

       pip install -r requirements/static/ci/py{python_version}/tools.txt

#. (Optional) To build a specific Salt version, you will need to install changelog dependencies:

    .. code-block:: bash

       pip install -r requirements/static/ci/py{python_version}/changelog.txt

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

       pip install -r requirements/static/ci/py{python_version}/tools.txt

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

       pip install -r requirements/static/ci/py{python_version}/tools.txt

#. Build the MacOS package:

    Only the arch and salt-version arguments are required, the rest are optional.
    Do note that you will not be able to sign the packages when building them.

    .. code-block:: bash

       tools pkg build windows --salt-version <salt-version> --arch <arch>


How to access python binary
===========================

The python library is available in the install directory of the onedir package. For example
on linux the default location would be ``/opt/saltstack/salt/bin/python3``.

Testing the packages
====================

If you want to test your built packages, or any other collection of salt packages post 3006.0, follow :ref:`this guide <pkging-testing>`

.. toctree::

     testing
