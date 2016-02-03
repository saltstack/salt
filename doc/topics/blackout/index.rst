.. _blackout:

=============================
Minion Blackout Configuration
=============================

.. versionadded:: 2016.3.0

Salt supports minion blackouts. When a minion is in blackout mode, all remote
execution commands are disabled. This allows production minions to be put
"on hold", eliminating the risk of an untimely configuration change.

Minion blackouts are configured via a special pillar key, ``minion_blackout``.
If this key is set to ``True``, then the minion will reject all incoming
commands, except for ``saltutil.refresh_pillar``. (The exception is important,
so minions can be brought out of blackout mode)
