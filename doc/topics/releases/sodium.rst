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
