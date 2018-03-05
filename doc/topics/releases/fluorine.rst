:orphan:

======================================
Salt Release Notes - Codename Fluorine
======================================


Minion Startup Events
---------------------

When a minion starts up it sends a notification on the event bus with a tag
that looks like this: `salt/minion/<minion_id>/start`. For historical reasons
the minion also sends a similar event with an event tag like this:
`minion_start`. This duplication can cause a lot of clutter on the event bus
when there are many minions. Set `enable_legacy_startup_events: False` in the
minion config to ensure only the `salt/minion/<minion_id>/start` events are
sent.

The new :conf_minion:`enable_legacy_startup_events` minion config option
defaults to ``True``, but will be set to default to ``False`` beginning with
the Neon release of Salt.

The Salt Syndic currently sends an old style  `sydic_start` event as well. The
syndic respects :conf_minion:`enable_legacy_startup_events` as well.
