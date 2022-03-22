What Is This All About
======================

This directory will contain platform specific requirements(and the requirements
of each requirements) locked to the versions used as if the testing environment
was setup using the salt-jenkins states.

The purpose of this is to ease the transition to `nox` and golden images where
only binary system packages are installed on the golden image and `nox`
installs the python dependencies on virtualenv specifically created for the
test run.

This will also make sure we run the tests with the exact same dependencies
every time.
