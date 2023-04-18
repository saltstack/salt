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
The Salt Project uses docker containers to build our packages. If you are building your own packages you can use
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

       relenv fetch --python=<pythonversion>

#. Create relenv environment:

    .. code-block:: bash

       relenv create --python=3.10.10 <relenv name>

#. Add Salt into onedir.

    .. code-block:: bash

       path/to/<relenv-name>/bin/pip install /path/to/salt


How to build rpm packages
=========================
#. Install the dependencies:

    .. code-block:: bash

       yum -y install python3 python3-pip openssl git rpmdevtools rpmlint systemd-units libxcrypt-compat git

#. (Optional) To build a specific Salt version, you will need to install tools and changelog dependencies:

    .. code-block:: bash

       pip install -r requirements/static/ci/py{python_version}/tools.txt

    .. code-block:: bash

       pip install -r requirements/static/ci/py{python_version}/changelog.txt

#. Ensure you are in the current Salt cloned git repo:

    .. code-block:: bash

       cd salt

#. (Optional) To build a specific Salt version, run tools and set Salt version:

    .. code-block:: bash

       tools changelog update-rpm <salt version>

#. Run rpmbuild in the Salt repo:

    .. code-block:: bash

        rpmbuild -bb --define="_salt_src $(pwd)" $(pwd)/pkg/rpm/salt.spec


How to build deb packages
=========================

#. Install the dependencies:

    .. code-block:: bash

       apt install -y bash-completion build-essential debhelper devscripts git patchelf python3 python3-pip python3-venv rustc

#. (Optional) To build a specific Salt version, you will need to install tools and changelog dependencies:

    .. code-block:: bash

       pip install -r requirements/static/ci/py{python_version}/tools.txt

    .. code-block:: bash

       pip install -r requirements/static/ci/py{python_version}/changelog.txt

#. Ensure you are in the current Salt cloned git repo.:

    .. code-block:: bash

       cd salt

#. (Optional) To build a specific Salt version, run tools and set Salt version:

    .. code-block:: bash

       tools changelog update-deb <salt version>


#. Add a symlink and run debuild in the Salt repo:

    .. code-block:: bash

        ln -sf pkg/debian/ .
        debuild -uc -us


How to access python binary
===========================

The python library is available in the install directory of the onedir package. For example
on linux the default location would be ``/opt/saltstack/salt/bin/python3``.
