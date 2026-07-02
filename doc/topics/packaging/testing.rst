.. _pkging-testing:

================
Testing packages
================

The package test suite
======================

The salt repo provides a test suite for testing basic functionality of our
packages at ``<repo-root>/pkg/tests/``. You can run the install, upgrade, and
downgrade tests. These tests run automatically on most PRs that are submitted
against Salt.


.. warning::

    These tests make destructive changes to your system because they install the
    built packages onto the system. They may also install older versions in the
    case of upgrades or downgrades. To prevent destructive changes, run the
    tests in an isolated system, preferably a virtual machine.

Setup
=====
In order to run the package tests, the `relenv
<https://github.com/saltstack/relative-environment-for-python>`_ onedir and
built packages need to be placed in the correct locations.

* Place all salt packages for the applicable testing version in
  ``<repo-root>/artifacts/pkg/``.
* The onedir must be located under ``<repo-root>/artifacts/``.
* Additionally, to ensure complete parity with Salt's CI/CD suite, place the
  ``nox`` virtual environment in ``<repo-root>/.nox/test-pkgs-onedir``.

The following are a few ways this can be accomplished easily.

You can ensure parity by installing the package test suite through a few
possible methods:

* Using ``tools``
* Downloading individually

Using ``tools``
---------------
Salt has preliminary support for setting up the package test suite in the
``tools`` command suite that is located under ``<repo-root>/tools/testsuite/``.
This method requires the Github CLI tool ``gh`` (https://cli.github.com/) to be properly configured for
interaction with the salt repo.

#. Install the dependencies using this command:

    .. code-block:: bash

       pip install -r requirements/static/ci/py{python_version}/tools.lock

#. Download and extract the artifacts with this ``tools`` command:


    .. code-block:: bash

        tools ts setup --platform {linux|darwin|windows} --slug
        <operating-system-slug> --pr <pr-number> --pkg

    The most common use case is to test the packages built on a CI/CD run for a
    given PR. To see the possible options for each argument, and other ways to
    utilize this command, use the following:

    .. code-block:: bash

        tools ts setup -h

.. warning::

    You can only download artifacts from finished workflow runs. This is something
    imposed by the GitHub API.
    To download artifacts from a running workflow run, you either have to wait for
    the finish or cancel it.

Downloading individually
------------------------
If the ``tools ts setup`` command doesn't work, you can download, unzip, and
place the artifacts in the correct locations manually. Typically, you want to
test packages built on a CI/CD run for a given PR. This guide explains how to
set up for running the package tests using those artifacts. An analogous process
can be performed for artifacts from nightly builds.

#. Find and download the artifacts:

    Under the summary page for the most recent actions run for that PR, there is
    a list of available artifacts from that run that can be downloaded. Download
    the package artifacts by finding
    ``salt-<major>.<minor>+<number>.<sha>-<arch>-<pkg-type>``.  For example, the
    amd64 deb packages might look like:
    ``salt-3006.2+123.01234567890-x86_64-deb``.

    The onedir artifact will look like
    ``salt-<major>.<minor>+<number>.<sha>-onedir-<platform>-<arch>.tar.xz``. For
    instance, the macos x86_64 onedir may have the name
    ``salt-3006.2+123.01234567890-onedir-darwin-x86_64.tar.xz``.

    .. note::

        Windows onedir artifacts have ``.zip`` extensions instead of ``tar.xz``

    While it is optional, it is recommended to download the ``nox`` session
    artifact as well.  This will have the form of
    ``nox-<os-name>-test-pkgs-onedir-<arch>``. The amd64 Ubuntu 20.04 nox
    artifact may look like ``nox-ubuntu-20.04-test-pkgs-onedir-x86_64``.

#. Place the artifacts in the correct location:

    Unzip the packages and place them in ``<repo-root>/artifacts/pkg/``.

    You must unzip and untar the onedir packages and place them in
    ``<repo-root>/artifacts/``. Windows onedir requires an additional unzip
    action. If you set it up correctly, the ``<repo-root>/artifacts/salt``
    directory then contains the uncompressed onedir files.

    Additionally, decompress the ``nox`` artifact and place it under
    ``<repo-root>/.nox/``.

Running the tests
=================
You can run the test suite run if all the artifacts are in the correct location.

.. note::

    You need root access to run the test artifacts. Run all nox commands at the
    root of the salt repo and as the root user.

#. Install ``nox``:

    .. code-block:: bash

        pip install nox

#. Run the install tests:

    .. code-block:: bash

        nox -e test-pkgs-onedir -- install

#. Run the upgrade or downgrade tests:

    .. code-block:: bash

        nox -e test-pkgs-onedir -- upgrade --prev-version <previous-version>

    You can run the downgrade tests in the same way, replacing ``upgrade`` with
    ``downgrade``.

    .. note::

        If you are testing upgrades or downgrades and classic packages are
        available for your system, replace ``upgrade`` or
        ``downgrade`` with ``upgrade-classic`` or ``downgrade-classic``
        respectively to test against those versions.

Running a single test
=====================

The package tests are pytest tests under ``pkg/tests/``. To run a single
test, pass its node ID after the ``--`` separator:

.. code-block:: bash

    nox -e test-pkgs-onedir -- install pkg/tests/integration/test_pip.py::test_pip_install

Use ``-k`` to filter by name:

.. code-block:: bash

    nox -e test-pkgs-onedir -- install -k test_pip

Add ``-vv -s`` to see live output and tracebacks.

Environment variables
=====================

The package test session reads a handful of variables from the environment:

============================== ===============================================
Variable                       Purpose
============================== ===============================================
``SALT_RELEASE``               Override the version string reported by tests.
``SALT_REPO_DOMAIN_RELEASE``   Override the repo domain used for downgrade /
                               upgrade-classic tests (default
                               ``repo.saltproject.io``).
``SALT_REPO_DOMAIN_STAGING``   Same as above for staging repos.
``DOWNLOAD_TEST_PACKAGES``     Set to ``1`` to let the test session fetch the
                               artifacts itself from the configured repo
                               instead of using the locally staged
                               ``<repo-root>/artifacts/pkg/``.
============================== ===============================================

Common failures
===============

* ``artifacts/salt`` is missing. The onedir tarball was not extracted into
  ``<repo-root>/artifacts/``. Re-run ``tools ts setup`` or extract the
  ``salt-<version>-onedir-<platform>-<arch>.tar.xz`` manually.

* ``salt-minion service failed to start`` on Debian. The default ``salt``
  user already exists with a non-matching home directory. Pre-set
  ``SALT_HOME`` in ``/etc/default/salt-setup`` before installing the package.

* ``module not found: <something>`` in an upgrade test. The ``extras-3.N``
  directory ownership was not restored on upgrade. Confirm that
  ``SALT_EXTRAS_DIR`` (if set) is owned by the same user that was running
  ``salt-pip``.

CI parity
=========

Each test session matches a ``slug`` in the
``salt-ci-containers/custom/packaging`` container set. To reproduce a CI
failure locally, use the same container image and the same artifacts the
CI run produced:

.. code-block:: bash

    docker run --rm -it -v "$PWD:/salt" -w /salt \
        ghcr.io/saltstack/salt-ci-containers/packaging:ubuntu-22.04 \
        bash -c 'pip install nox && nox -e test-pkgs-onedir -- install'

The container ships the OS-level build dependencies and matches the
``test-pkgs-onedir`` Python pin used in CI.
