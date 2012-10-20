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
