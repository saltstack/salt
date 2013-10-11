Running The Tests
=================

To run the tests, use ``tests/runtests.py``, see ``--help`` for more info.

Examples:

* To run all tests: ``sudo ./tests/runtests.py``
* Run unit tests only: ``sudo ./tests/runtests.py --unit-tests``

You will need 'mock' (https://pypi.python.org/pypi/mock) in addition to salt requirements in order to run the tests.

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
