.. _resources-authoring-pillar:

==============
Pillar layout
==============

Resources live in pillar under a configurable top-level key. The
managing minion reads that subtree on startup and on every pillar
refresh to discover which resource types it manages, which resource
ids exist for each type, and any per-resource configuration the type
needs.


The pillar subtree
==================

Default key: ``resources``. Configurable via
:conf_minion:`resource_pillar_key`. The subtree's first level is the
**resource type**, the second level is whatever the resource type
wants to define:

.. code-block:: yaml

    resources:
      ssh:
        hosts:
          web-01:
            host: 10.0.0.10
            user: admin
            priv: /etc/salt/keys/web-01
          web-02:
            host: 10.0.0.11
            user: admin
            priv: /etc/salt/keys/web-02

      dummy:
        resource_ids:
          - dummy-01
          - dummy-02

      widget:
        hosts:
          w1:
            endpoint: https://widgets.example.com/w1
            token_pillar: widget_w1_token

Each top-level key is the type's discovery namespace. The shape under
that key is **type-specific** — the framework doesn't impose one. Two
common conventions:

``resource_ids: [...]``
   A flat list of ids. Best when nothing per-id is needed in pillar
   (the resource type fetches per-id configuration from elsewhere, or
   doesn't need any).

``hosts: {id: {...}}``  *(or any single dict)*
   A dict keyed by resource id, with per-id config alongside. Use this
   when the connection module needs per-resource configuration in
   pillar (credentials, endpoint URLs, paths). The shape under each
   id is yours to design.


Reading pillar from a resource type
===================================

Use :py:func:`salt.utils.resources.pillar_resources_tree` to fetch the
configured subtree. It honours :conf_minion:`resource_pillar_key`
without you having to look it up::

    import salt.utils.resources

    def discover(opts):
        return list(
            salt.utils.resources.pillar_resources_tree(opts)
            .get("widget", {})
            .get("hosts", {})
            .keys()
        )

    def init(opts):
        widget_pillar = salt.utils.resources.pillar_resources_tree(opts).get("widget", {})
        __context__["widget"] = {
            "initialized": True,
            "hosts": widget_pillar.get("hosts", {}),
        }


Picking a custom pillar key
===========================

If the default ``resources`` key collides with existing pillar in your
environment, override it in the minion config:

.. code-block:: yaml

    # /etc/salt/minion.d/resources.conf
    resource_pillar_key: salt_resources

Two rules:

1. Use the *same key* on every minion in a master. Targeting on the
   master assumes the master can read each minion's resources subtree
   under one consistent key.
2. Use a non-empty string. Setting the key to ``""`` logs a warning
   and falls back to the default.


Secrets and pillar masking
==========================

.. versionchanged:: 3008.0

Salt 3008.0 introduced pillar masking: ``pillar.get`` from the CLI
returns ``'**********'`` for string values by default. Templates and
SLS files render with masking disabled so they see plain values, so
your resource type's ``init(opts)`` reading pillar via
:py:func:`salt.utils.resources.pillar_resources_tree` continues to see
real values.

If you write an integration test that calls ``pillar.get`` from the
CLI and compares against a real value, pass ``unmask=True``::

    salt-call pillar.get resources:widget:hosts unmask=True


Examples in the wild
====================

* ``salt/resources/dummy/__init__.py`` — ``resource_ids: [...]`` shape.
* ``salt/resources/ssh/__init__.py`` — ``hosts: {id: {...}}`` shape
  with credentials and connection details per id.
