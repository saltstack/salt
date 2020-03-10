:orphan:

====================================
Salt Release Notes - Codename Sodium
====================================


Salt mine updates
=================

Syntax update
-------------

The syntax for defining salt functions in config or pillar files has changed to
also support the syntax used in :py:mod:`module.run <salt.states.module.run>`.
The old syntax for the mine_function - as a dict, or as a list with dicts that
contain more than exactly one key - is still supported but discouraged in favor
of the more uniform syntax of module.run.

State Execution Module
======================

The :mod:`state.test <salt.modules.state.test>` function
can be used to test a state on a minion. This works by executing the
:mod:`state.apply <salt.modules.state.apply>` function while forcing the ``test`` kwarg
to ``True`` so that the ``state.apply`` function is not required to be called by the
user directly. This also allows you to add the ``state.test`` fucntion to a minion's 
``minion_blackout_whitelist`` pillar if you wish to be able to test a state while a
minion is in blackout.
