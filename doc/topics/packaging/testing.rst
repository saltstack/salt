.. _pkging-testing:

================
Testing Packages
================

The Package Test Suite
======================

The salt repo provides a test suite for testing basic functionality of our packages at ``<repo-root>/pkg/tests/``.
The install, upgrade, and downgrade tests can be run locally, and are run on most PRs that are submitted against Salt.


.. warning::

    These tests are destructive to your system, as they install the built packages onto the
    system, and can also install older versions in the case of upgrades or downgrades.
    It is recommended to run these in an isolated system, preferrably a VM.

Setup
=====
In order to run the package tests, the `relenv <https://github.com/saltstack/relative-environment-for-python>`_
onedir and built pacakges need to be placed in the correct locations.

All salt packages for the wanted testing version must be placed in ``<repo-root>/pkg/artifacts``,
and the onedir must be located at ``<repo-root>/artifacts/salt``. Additionally, to ensure complete parity with Salt's CI/CD
suite, the ``nox`` virtual environment can be placed at ``<repo-root>/.nox/test-pkgs-onedir`` The following are a few ways this can be accomplished easily.

Using ``tools``
---------------
There is preliminary support for setting up the package test suite in the ``tools`` command suite that is located under ``<repo-root>/tools/testsuite``.
This does require the Github CLI tool ``gh`` to be properly configured for interaction with the salt repo.

#. Install the dependencies

    .. code-block:: bash

       pip install -r requirements/static/ci/py{python_version}/tools.txt

#. Download and lay down the artifacts

    The most common use case is to test the packages built on a CI/CD run for a given PR.

    .. code-block:: bash

        tools ts setup --platform {linux|darwin|windows} --slug <operating-system-slug> --pr <pr-number> --pkg

    To see the possible options for each argument, and other ways to utilize this command, use the following.

    .. code-block:: bash

        tools ts setup -h


Downloading Individually
------------------------
If the ``tools ts setup`` command doesn't quite work, the artifacts can be downloaded, unzipped, and placed in the correct locations manually.
Most often, you will be testing packages built on a CI/CD run for a given PR. This guide will explain how to setup for running the package tests using those artifacts.
An analogous process can be performed for artifacts from nightly builds.

#. Download the artifacts

    Under the summary page for the most recent actions run for that PR, there is a list of available artifacts from that run that can be downloaded.
    Download the package artifacts by finding ``salt-<major>.<minor>+<number>.<sha>-<arch>-<pkg-type>``.  For example, the x86_64 deb packages
    might look like ``salt-3006.2+123.01234567890-x86_64-deb``.

    The onedir artifact will look like ``salt-<major>.<minor>+<number>.<sha>-onedir-<platform>-<arch>.tar.xz``.
    For instance, the macos x86_64 onedir may have the name ``salt-3006.2+123.01234567890-onedir-darwin-x86_64.tar.xz``.

    .. note::

        Windows onedir artifacts have ``.zip`` extensions instead of ``tar.xz``

    While it is optional, it is recommended to download the ``nox`` session artifact as well.  This will have the form of ``nox-<os-name>-test-pkgs-onedir-<arch>``.
    The x86_64 Ubuntu 20.04 nox artifact may look like ``nox-ubuntu-20.04-test-pkgs-onedir-x86_64``.

#. Placing the artifacts in the correct location

    The packages should be unzipped and placed under ``<repo-root>/pkg/artifacts``.

    The onedir artifact must be unzipped and untarred (or unzipped again, for windows onedirs) under ``<repo-root>/artifacts``.
    There should then be a ``<repo-root>/artifacts/salt`` directory that contains the uncompressed onedir.

    Lastly, the ``nox`` artifact should be fully uncompressed and placed under ``<repo-root>/.nox``.

Running the Tests
=================
Once all the artifacts are in the correct locations, the test suite can now be run.

.. note::

    All nox commands should be run at the root of the salt repo and as the root user.

#. Install ``nox``

    .. code-block:: bash

        pip install nox

#. Run the install tests

    .. code-block:: bash

        nox -e test-pkgs-onedir -- install

#. Run the upgrade or downgrade tests

    .. code-block:: bash

        nox -e test-pkgs-onedir -- upgrade --prev-version <previous-version>

    The downgrade tests can be run in the same way, replacing ``upgrade`` with ``downgrade``.

    .. note::

        If the previous version being tested is before 3006.0 and there are classic packages available for your system,
        append ``-classic`` to ``upgrade`` or ``downgrade`` to test against those versions.
