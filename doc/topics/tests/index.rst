=================
Running The Tests
=================

There are requirements, in addition to Salt's requirements, which
needs to be installed in order to run the test suite. Install one of
the lines below, depending on the relevant Python version:

.. code-block:: bash

    pip install -r dev_requirements_python26.txt
    pip install -r dev_requirements_python27.txt

.. note::

    In Salt 0.17, testing libraries were migrated into their own repo. To install them:

     .. code-block:: bash

         pip install git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting


    Failure to install SaltTesting will result in import errors similar to the following:

     .. code-block:: bash

        ImportError: No module named salttesting

Once all require requirements are set, use ``tests/runtests.py`` to
run the tests, see ``--help`` for more info.

And alternative way of invoking the tests is available in setup.py,
run the tests with the following command:

.. code-block:: bash

    ./setup.py test

Examples:

* Run unit tests only: ``sudo ./tests/runtests.py --unit-tests``
* Run a specific set of integration tests only: ``sudo ./tests/runtests.py -n integration.modules.virt -vv``
* Run a specific set of unit tests only: ``./tests/runtests.py -n unit.modules.virt_test -vv``


Running The Tests In A Docker Container
=======================================

If the ``runtests.py`` binary supports the ``--docked`` option flag, you can
choose to execute the tests suite under the provided `docker`_ container. You
need to have your `docker`_  properly configured on your system and the
containers need to have access to the internet.

Here's a simple usage example:

.. code-block:: bash

    tests/runtests.py --docked=ubuntu-12.04 -v

You can also provide the full `docker` container repository:

.. code-block:: bash

    tests/runtests.py --docked=salttest/ubuntu-12.04 -v


The SaltStack team is creating some containers which will have the necessary
dependencies pre-installed allowing you, for example, to run the destructive
tests without making a single destructive change to your system, or, to run the
tests suite under a different distribution than the one you're currently using.

You can see the current list of test suite images on our `docker repository`__.

If you wish to provide your own `docker`_ container, you can submit pull
requests against our `docker salt test containers`__ repository.

.. _docker: http://www.docker.io/
.. __: https://index.docker.io/u/salttest/
.. __: https://github.com/saltstack/docker-salttest-containers


=============
Writing Tests
=============

Salt uses a test platform to verify functionality of components in a simple
way. Two testing systems exist to enable testing salt functions in somewhat
real environments. The two subsystems available are integration tests and
unit tests.

Salt uses the python standard library unittest2 system for testing.

Integration Tests
=================

The integration tests start up a number of salt daemons to test functionality
in a live environment. These daemons include 2 salt masters, 1 syndic and 2
minions. This allows for the syndic interface to be tested and master/minion
communication to be verified. All of the integration tests are executed as
live salt commands sent through the started daemons.

* :doc:`Writing integration tests <integration>`

Integration tests are particularly good at testing modules, states and shell
commands.

Unit Tests
==========

Direct unit tests are also available, these tests are good for internal
functions.

* :doc:`Writing unit tests <unit>`
