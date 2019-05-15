.. _blackout:

=============================
Minion Blackout Configuration
=============================

.. versionadded:: 2016.3.0

Salt supports minion blackouts. When a minion is in blackout mode, all remote
execution commands are disabled. This allows production minions to be put
"on hold", eliminating the risk of an untimely configuration change.

Minion blackouts are configured two ways either via a special pillar key, ``minion_blackout``.
or a special grains key ``minion_blackout``.
If this key is set to ``True``, then the minion will reject all incoming
commands, except for ``saltutil.refresh_pillar``. (The exception is important,
so minions can be brought out of blackout mode)

Salt also supports an explicit whitelist of additional functions that will be
allowed during blackout. This is configured two ways as well. Either with the special pillar key
or the special grains key ``minion_blackout_whitelist``, which is formed as a list:

.. code-block:: yaml

    minion_blackout_whitelist:
     - test.version
     - pillar.get

When use a special pillar key ``minion_blackout`` then salt will get ``minion_blackout_whitelist`` from the
pillar keys. And will get it from the grains when use ``minion_blackout`` as a special grains key.
You therefore can strictly control ``minion_blackout`` status and ``minion_blackout_whitelist`` content by a minion side
when you use a special grains key. A special grains key ``blackout_mode`` has higher priority
than a special pillar key ``blackout_mode```
