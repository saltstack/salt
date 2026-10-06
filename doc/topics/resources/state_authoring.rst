.. _resources-state-authoring:

================================
States against Salt Resources
================================

.. versionadded:: 3008.0

How ``state.apply``, ``state.highstate``, and ``state.sls`` behave when
they target resources. This page is the *runtime* counterpart to the
:ref:`state-module authoring guide <resources-authoring-states>` — read
that one if you're writing state modules, this one if you're applying
states or trying to debug what's going on.


The merge-mode contract
=======================

These functions are special:

* ``state.apply``
* ``state.highstate``
* ``state.sls``
* ``state.sls_id``
* ``state.single``

(The full list lives in
:py:attr:`~salt.minion.Minion._MERGE_RESOURCE_FUNS`.)

When the operator runs one of them against a target that includes
resources — ``salt -C 'T@ssh' state.apply mysls``, say — Salt does
**not** dispatch one independent return per resource. Instead:

1. The master's wait list contains the *managing minion* id, not the
   resource ids.
2. The managing minion runs the per-resource apply **inline** —
   building one ``HighState`` per matched resource using that
   resource's per-type loader.
3. The managing minion folds the per-resource state IDs into a single
   ``ret["return"]`` dict and publishes one combined return.
4. The CLI prints one block + one Summary, with each state ID
   prefixed by its resource id so provenance is visible.

This matches how any other minion looks to the master: one publish,
one return, one block of output. The difference is invisible to
``state.show_lowstate`` and friends.


State-ID prefixing
==================

Salt's state low keys are ``{module}_|-{id}_|-{name}_|-{function}``.
When the managing minion folds per-resource results into the parent
dict, it rewrites positions 1 and 2 (id and name) with the resource id
prepended. So a state declared as

.. code-block:: yaml

    install_curl:
      pkg.installed:
        - name: curl

apply'd against ``T@ssh:web-01`` and ``T@ssh:web-02`` produces two
keys::

    pkg_|-web-01 install_curl_|-web-01 curl_|-installed
    pkg_|-web-02 install_curl_|-web-02 curl_|-installed

The ``{module}`` (``pkg``) and ``{function}`` (``installed``)
positions are left alone so the highstate formatter still shows
``Function: pkg.installed`` correctly; only the ID and Name are
relabelled to surface the resource.

If a resource fails before the per-resource ``HighState`` produced any
chunks (e.g. the resource type couldn't fulfil the operation at all),
the framework inserts a synthetic chunk under
``no_|-{rid}_|-{rid}_|-None`` so the result is still visible in the
combined dict and still contributes to the overall pass/fail.

You don't have to think about prefixing inside your states. Just keep
state IDs stable across resources and the output will be readable.


The managing minion is NOT a target (usually)
==============================================

For ``T@`` and ``M@`` compound expressions that *only* address
resources (a "pure resource target"), the managing minion is *not* a
target for the function itself — its job is to run the resources
inline, not to apply the state to its own filesystem.

The framework detects this case via ``data["pure_resource_target"]``
in :py:meth:`~salt.minion.Minion._thread_return` and **skips** the
regular function execution on the managing minion. Without that skip
you'd see a spurious ``"state.apply not found"`` block from the
managing minion alongside the real per-resource results.

If the target expression *also* matches the managing minion (a wildcard
glob like ``salt '*' state.apply``, or a grain match the host also
satisfies), the managing minion runs the apply against itself too —
its results appear in the combined dict alongside the per-resource
results.


The ``__minion__`` escape hatch
================================

Inside per-resource state code, ``__salt__`` is the *per-resource*
execution loader. That's almost always what you want — it gives you
both your overrides (where they exist) and the standard module set
(everywhere else).

Occasionally a state needs to do something *on the managing minion
itself* — write a checkpoint to ``/var/lib/salt/`` after each resource
finishes, look up a credential from the host's keychain, etc. That's
what ``__minion__`` is for. It's the managing minion's regular
execution-module loader, packed into per-resource state and execution
modules as an explicit escape hatch::

    def post_widget_apply(name, **kwargs):
        ret = {"name": name, "result": True, "changes": {}, "comment": ""}

        widget_status = __salt__["widget.status"](name)
        if widget_status.get("ok"):
            __minion__["file.append"](
                "/var/lib/salt/widget-applied.log",
                f"{name} applied successfully\n",
            )
            ret["comment"] = "Recorded apply on managing minion"
        else:
            ret["result"] = False
            ret["comment"] = "Widget not in OK state"

        return ret

Reach for ``__minion__`` deliberately. It is a deliberate cross-context
call: the state is running in resource context but reaches back to the
host. State module authors should think of it the way they'd think of
running ``subprocess.run`` from a state function — fine when it's the
right answer, a smell when used by reflex.


When ``state.apply`` falls through to the standard module
==========================================================

For resource types **without** a per-type override of the ``state``
slot (no ``salt/resources/<rtype>/modules/state.py``), the standard
``salt.modules.state`` module runs in the per-resource loader. That
means:

* ``__salt__["state.apply"]`` for that resource compiles the high
  state on the **managing minion**, using the **per-resource
  execution loader** for ``__salt__`` inside the rendered states.
* The states themselves run on the managing minion (because that's
  where the state engine is) but every module call inside them
  dispatches via the per-resource loader.

For resource types that ship a per-type ``state.py`` (today: the
``ssh`` resource), ``state.apply`` runs *on the resource itself* via
whatever transport the override implements.

Both shapes converge at the same return contract — per-resource state
results folded into the managing minion's combined return.


Debugging tips
==============

* **Where is my state running?** Look at the ``minion`` field in the
  highstate output. For resource types without a state override it's
  the managing minion (with per-resource ``__salt__``). For types
  with a state override it's "wherever the override sends it" — for
  the SSH resource type, that's the remote host over SSH.
* **State ID collisions in output.** If two different resources
  produce the same state ID *after* the rid prefix, you have a
  prefixing bug — usually a state ID that contains characters Salt
  treats specially in the low-key encoding. File a bug.
* **"State X is not available."** Means the per-resource loader has
  no module providing slot ``X``. Either ship an override at
  ``<rtype>/modules/X.py`` or use a different state.


Related
=======

* :ref:`resources-architecture` — registry, dispatch, merge mode.
* :ref:`resources-authoring-states` — how to write state overrides.
* :ref:`resources-authoring-execution` — how the per-resource ``__salt__``
  is built.
