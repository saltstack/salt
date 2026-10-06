.. _resources-authoring:

================================
Authoring a Salt resource type
================================

.. versionadded:: 3008.0

This guide walks through the files, dunders, and conventions that make a
resource type work. The reference implementation it mirrors is
:py:mod:`salt.resources.dummy`, which exists for exactly this purpose.

A resource type is just a Python package. Where you put it depends on
where you ship it:

* **In core Salt** — under ``salt/resources/<rtype>/``.
* **In an extension** — under ``saltext/<ext>/resources/<rtype>/`` in a
  package that declares the ``salt.loader`` entry point. Salt's loader
  discovers it automatically.

The directory layout is the same either way:

.. code-block:: text

   <rtype>/
       __init__.py        # connection module: init, grains, helpers
       modules/           # execution-module overrides
       states/            # state-module overrides
       grains/            # grain modules (rarely needed)

Most of this guide is "drop a file at the right path with the right
function names". The framework does not require subclassing anything;
overrides win their slot by filename and directory order. The dunders
the loader packs into each module are documented below.


Topics
======

.. toctree::
   :maxdepth: 1

   connection_module
   execution_modules
   state_modules
   pillar
   packaging


Quick start
===========

The shortest possible resource type. Three files:

``saltext/myext/resources/widget/__init__.py``::

    def __virtual__():
        return True

    def init(opts):
        __context__["widget"] = {"initialized": True}

    def initialized():
        return __context__.get("widget", {}).get("initialized", False)

    def discover(opts):
        import salt.utils.resources
        return list(
            salt.utils.resources.pillar_resources_tree(opts)
            .get("widget", {})
            .get("resource_ids", [])
        )

    def grains():
        return {"widget_id": __resource__["id"]}

    def ping():
        return True

    def shutdown(opts):
        __context__.pop("widget", None)

``saltext/myext/resources/widget/modules/test.py``::

    def ping():
        return "pong from widget"

``saltext/myext/__init__.py``::

    # empty, makes saltext.myext a package

Plus a ``pyproject.toml`` entry point that points the Salt loader at
your package (see :doc:`packaging`).

With that in place — and the minion's pillar containing
``resources: {widget: {resource_ids: [w1, w2]}}`` — ``salt -C
'T@widget' test.ping`` returns ``"pong from widget"`` for both
``w1`` and ``w2``.

Read on for the full interface contract and the override mechanics.
