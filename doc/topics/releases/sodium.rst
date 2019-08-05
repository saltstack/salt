:orphan:

====================================
Salt Release Notes - Codename Sodium
====================================


Salt mine updates
=================

Syntax update
-------------

The syntax for defining salt functions in config or pillar files has changed to
be equal to the syntax used in :py:mod:`module.run <salt.states.module.run>`.
This means that if you supply the mine_function as a dict, or as a list with dicts
that contain more than exactly one key, you will get deprecation warnings.

Minion-side ACL
---------------

Salt has had master-side ACL for the salt mine for some time, where the master
configuration contained `mine_get` that specified which minions could request
which functions. However, now you can specify which minions can access a function
in the salt mine function definition itself (or when calling :py:func:`mine.send <salt.modules.mine.send>`).
This targeting works the same as the generic minion targeting as specified
:ref:`here <targeting>`. The parameters used are ``allow_tgt`` and ``allow_tgt_type``.
See also :ref:`the documentation of the Salt Mine <mine_minion-side-acl>`.
