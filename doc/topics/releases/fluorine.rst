:orphan:

======================================
Salt Release Notes - Codename Fluorine
======================================

State Module Changes
====================

states.saltmod
--------------
The 'test' option now defaults to None. A value of True or False set here is 
passed to the state being run and can be used to override a ``test:True`` option
set in the minion's config file. In previous releases the minion's config option
would take precedence and it would be impossible to run an orchestration on a
minion with test mode set to True in the config file.

If a minion is not in permanent test mode due to the config file and the 'test'
argument here is left as None then a value of ``test=True`` on the command-line is
passed correctly to the minion to run an orchestration in test mode. At present
it is not possible to pass ``test=False`` on the command-line to override a
minion in permanent test mode and so the ``test:False`` option must still be set
in the orchestration file.
