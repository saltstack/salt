.. _resources-authoring-connection:

=================
Connection module
=================

The ``__init__.py`` of a resource type is the **connection module**.
It owns three jobs:

1. Tell the managing minion which resource ids it manages
   (``discover``).
2. Establish whatever per-resource state is needed before any call
   (``init`` + ``initialized``).
3. Produce per-resource grains (``grains`` + ``grains_refresh``).

A handful of optional hooks (``ping``, ``shutdown``, custom execution
functions) round it out.


Required interface
==================

Every connection module must define:

``__virtual__()``
   Standard Salt loader hook. Return ``True`` (or your virtualname) if
   the type can be loaded on this minion; return ``(False, "reason")``
   to opt out. Resource types typically return ``True`` unconditionally
   — the loader is only consulted when the pillar names the type.

``init(opts)``
   Called once when the type is loaded, before any per-resource
   operations run. Reads the resource type's pillar subtree and seeds
   any shared state in ``__context__``. Idempotent.

``initialized()``
   Returns ``True`` if ``init()`` has run successfully. The framework
   checks this before dispatching per-resource operations so a partial
   ``init`` failure doesn't produce bogus results.

``discover(opts)``
   Returns the list of bare resource ids (not full SRNs) that this
   minion manages for this type. Called by ``saltutil.refresh_resources``
   and by minion startup. Read from pillar — typically the
   ``resource_ids`` key under the type's subtree.

``grains()``
   Returns the grain dict for the *currently dispatched* resource. The
   current resource is in ``__resource__`` (see :ref:`Dunders
   <resources-authoring-dunders>` below). What you put here is what
   ``-G key:value`` will match against; keep it small and tag-like
   (env, role, region) rather than re-reading the world on every
   target check.


Optional interface
==================

``ping()``
   Reachability probe for the current resource. Used by
   :py:func:`salt.modules.test.ping` overrides and operator tools.

``grains_refresh()``
   Invalidate any cached grain state and recompute. The default loader
   calls ``grains()`` again if you don't implement this; implement it
   only if you maintain your own cache layer.

``shutdown(opts)``
   Tear down type-level state from ``__context__``. Called when the
   minion shuts down or unloads the type.

Anything else you define in ``__init__.py`` is callable as a
per-resource execution function once the loader picks the module up.
Functions named with a verb-noun convention
(``service_start``, ``package_install``) tend to age well; if you want
them to take over a slot in the standard Salt module surface, put the
overrides in ``modules/`` instead (see
:ref:`resources-authoring-execution`).


.. _resources-authoring-dunders:

Dunders available in connection-module code
============================================

The loader packs these into your module's globals before any call:

``__opts__``
   The managing minion's opts dict — same as anywhere else in Salt.

``__context__``
   Per-loader transient dict. Use it for connection caches and the
   ``initialized`` flag.

``__resource__``
   ``{"type": "<rtype>", "id": "<resource-id>"}``. Set for every
   per-resource dispatch (grains, ping, custom funcs). Not set during
   ``init``, ``discover``, or ``shutdown`` — those run once per type,
   not once per resource.

``__pillar__``, ``__grains__``
   The *managing minion's* pillar and grains. The resource's own
   grains aren't yet available inside the connection module itself —
   they're what it produces.

``__salt__``
   The managing minion's standard execution-module loader. Useful for
   delegating to ``cmd.run`` or any other Salt function on the host
   that's doing the connecting.


Pattern: filesystem-backed dummy
================================

The reference implementation in :py:mod:`salt.resources.dummy` is a
fully self-contained example. It persists per-resource state to a
cache file and is wired up so that ``salt -C 'T@dummy' state.apply``
exercises every code path without needing real connectivity. Read it
when you start your own type.


Pattern: connection-per-resource cached in ``__context__``
==========================================================

For types that talk to a real remote service, build the connection
lazily and cache it keyed by resource id::

    def _connect(resource_id):
        conns = __context__.setdefault("widget", {}).setdefault("conns", {})
        if resource_id not in conns:
            cfg = (
                salt.utils.resources.pillar_resources_tree(__opts__)
                .get("widget", {})
                .get("hosts", {})
                .get(resource_id, {})
            )
            conns[resource_id] = WidgetClient(cfg)
        return conns[resource_id]

    def ping():
        return _connect(__resource__["id"]).ping()

The cache lives for the lifetime of the per-type loader (i.e. until
the minion reloads modules or the type is unregistered). The loader
calls ``shutdown(opts)`` on teardown so you can close connections
cleanly.


Mistakes to avoid
=================

* **Doing slow work in** ``grains()``. ``grains()`` is called on every
  registration and refresh. If you need to phone the resource to get
  the value, cache it in ``__context__`` and refresh deliberately.
* **Using** ``__resource__`` **in** ``init()``. ``init`` runs once per
  type, before any resource is selected; ``__resource__`` is unset.
  Use ``opts`` and the pillar instead.
* **Mutating** ``opts``. The opts dict is shared across the managing
  minion. Treat it as read-only — copy it if you need a per-resource
  variant.
* **Leaking transient state in** ``__context__``. Whatever you put in
  ``__context__`` persists across calls. Anything *connection-scoped*
  (auth tokens with TTLs, etc.) should track its own expiry.
