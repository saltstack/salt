.. _resources-authoring-states:

======================
State module overrides
======================

The ``states/`` directory of a resource type holds **state module
overrides**. The mechanics mirror :ref:`execution-module overrides
<resources-authoring-execution>` exactly: filename = state slot,
directory order picks the override when one exists, standard
``salt/states/`` fills any slot you don't override.

If you've followed the :ref:`architecture <resources-architecture>`
discussion of merge-mode ``state.apply``, this is where authoring meets
that machinery. See :ref:`resources-state-authoring` for the runtime
semantics; this page is about *writing* the modules.


When to add a state override
============================

Most resource types do **not** need state overrides. The standard
state modules (``pkg.installed``, ``service.running``, ``file.managed``,
…) call into ``__salt__`` for their actual work. If your resource type
ships the right *execution-module* overrides — so ``__salt__["pkg.install"]``
does the right thing on a widget — the standard ``pkg.installed``
state module runs unchanged against your resource.

Reach for a state override only when the *state semantics themselves*
differ — when "this resource is in state X" can't be expressed by
existing ``__salt__`` calls.


Dunders inside a state override
===============================

``__salt__``
   The per-resource execution loader. Calling ``__salt__["pkg.install"]``
   from inside a state runs the *per-resource* ``pkg.install`` if you
   have one, otherwise the standard module.

``__opts__``
   Read-only opts. ``opts["resource_type"]`` is set inside per-resource
   state apply — handy for state code that wants to know whether it's
   running against a resource at all.

``__grains__``
   The **resource's** grain dict.

``__minion__``
   The managing minion's execution-module loader. The escape hatch.
   Use this when a state genuinely needs to do something on the host
   — write a checkpoint to ``/var/lib/`` on the managing minion,
   say, after each resource finishes. See
   :ref:`resources-state-authoring` for when this is appropriate.

``__resource__``
   ``{"type": ..., "id": ...}`` for the resource the state is running
   against.


Pattern: forward to a connection-module function
================================================

A widget state that ensures a service is running on the widget::

    # states/service.py
    def running(name, **kwargs):
        ret = {
            "name": name,
            "result": False,
            "changes": {},
            "comment": "",
        }

        current = __salt__["widget.service_status"](name)
        if current.get("comment") == "running":
            ret["result"] = True
            ret["comment"] = f"Service {name} is already running"
            return ret

        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"Service {name} would be started"
            ret["changes"] = {name: {"old": "stopped", "new": "running"}}
            return ret

        __salt__["widget.service_start"](name)
        ret["result"] = True
        ret["comment"] = f"Service {name} started"
        ret["changes"] = {name: {"old": "stopped", "new": "running"}}
        return ret


Pattern: re-export a standard state module
==========================================

Same trick as for execution modules. Re-export with
``namespaced_function`` so the standard state's dunder resolution
happens against the per-resource loader::

    # states/file.py
    import salt.utils.functools
    import salt.states.file as _src

    managed   = salt.utils.functools.namespaced_function(_src.managed, globals())
    absent    = salt.utils.functools.namespaced_function(_src.absent, globals())
    directory = salt.utils.functools.namespaced_function(_src.directory, globals())

This is unusual — if your execution-module overrides are right, the
standard ``salt.states.file`` already works against the resource via
``__salt__``. Re-export only when the state module imports from
``salt.modules.*`` directly (some old state modules do) and you need
those imports rebound to the per-resource loader.


Merge mode and state IDs
========================

When the operator runs ``state.apply`` (or any other
:py:attr:`~salt.minion.Minion._MERGE_RESOURCE_FUNS` function) against
``T@<rtype>[:<id>]``, the managing minion runs each resource's state
apply inline and folds the per-resource state IDs into one combined
dict. The framework prefixes each state ID with the resource id so
operators see provenance in the output.

You don't have to do anything special in your state code for this to
work — it's handled in ``Minion._thread_return``. See
:ref:`resources-state-authoring` for the prefixing scheme and how to
keep your state IDs stable across resources.


Mistakes to avoid
=================

* **Calling** ``__minion__["..."]`` **by reflex**. ``__minion__`` is the
  escape hatch. Most state code wants ``__salt__`` — which resolves
  against the per-resource loader and gives you both resource
  overrides and standard modules. Only reach for ``__minion__`` when
  you genuinely need something to happen on the host, not the resource.
* **Returning** ``"changes"`` **that aren't dicts**. State returns
  must follow Salt's state-return contract. Resources don't relax that.
* **Side-effecting in** ``test=True`` **mode**. Same contract as core
  Salt — if ``__opts__["test"]`` is true, show the diff but don't
  apply it.
