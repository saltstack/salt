.. _resources-architecture:

============
Architecture
============

.. versionadded:: 3008.0

How Salt Resources actually work: where the data lives on the master,
how a publish reaches a resource, what runs where, and the seams an
operator or extension author can hook into.


Three sides, three responsibilities
===================================

* The **master** owns the system-of-record for which minion manages
  which resource. It uses that record to expand targeting expressions
  and to populate the job's wait list.
* The **managing minion** carries the connection plumbing, the
  per-resource grain dicts, and the per-resource execution and state
  loaders. It is the process that actually talks to the resource.
* The **resource type** is a Python package — in core Salt under
  :py:mod:`salt.resources` or in any Salt extension under
  ``saltext.<ext>.resources.<rtype>`` — that defines what *type of
  thing* the resource is and what operations it understands.


Master side: the resource registry
==================================

Source of record: :py:mod:`salt.utils.resource_registry`
--------------------------------------------------------

The master keeps an mmap-backed index of every resource any minion
currently manages. Each entry is a composite key (``"type:id"``, written
**SRN** for *Salt Resource Name*) mapping to a small JSON payload:

.. code-block:: json

   {"m": "<managing-minion-id>", "t": "<resource_type>"}

* The **primary index** (``by_id``) is a
  :class:`~salt.utils.mmap_cache.MmapCache` file on disk. Lookups and
  inserts are O(1) linear-probing hash operations.
* Two **derived secondaries** (``by_type``, ``by_minion``) are
  materialised in-process on first access and rebuilt when the master
  observes the primary file has been compacted.
* A separate ``resource_grains`` cache bank stores each resource's
  per-resource grain dict (one msgpack blob per SRN).

The registry is reused for three jobs:

1. **Expanding compound targets**. ``T@ssh`` walks ``by_type["ssh"]``;
   ``T@ssh:web-01`` reads ``by_id["ssh:web-01"]`` and gets back the
   managing minion id.
2. **Augmenting grain matches**.
   :func:`~salt.utils.minions.CkMinions._augment_grain_match_with_resource_grains`
   walks the ``resource_grains`` bank to find resources whose grain
   dict satisfies the operator's ``-G`` / ``G@`` expression and adds
   them to the response wait list.
3. **Picking the managing minion for merge-mode functions**. When the
   command is ``state.apply`` or another :ref:`merge fun
   <resources-arch-merge>`, the master returns the *managing minion's*
   id in the wait list instead of the resource id — the managing
   minion runs the apply inline and returns one combined block. See
   :ref:`resources-state-authoring`.


Writes
------

The only writer is the master worker's ``AESFuncs._register_resources``
handler (called by the minion's ``_register_resources_with_master``).
Every register call:

1. Diffs the minion's previous registration against the new payload.
2. Drops entries for resources the minion no longer manages.
3. Inserts or refreshes entries for resources the minion does manage.
4. Updates ``resource_grains`` for any resource whose grain dict
   changed.

Re-registration triggers — what causes the master's view to refresh —
are documented in :ref:`resources-operations`.


Minion side: per-resource loaders
=================================

Discovery
---------

On startup and on every pillar refresh, the managing minion reads its
pillar subtree at :conf_minion:`resource_pillar_key` (default
``resources``). For each resource type ``<rtype>`` listed there, it:

1. Imports the resource module — ``salt.resources.<rtype>`` for
   in-tree types, or ``saltext.<ext>.resources.<rtype>`` for
   extension-shipped types.
2. Calls the module's ``init(opts)`` for each declared resource id —
   establishing the connection or doing whatever per-resource setup the
   type requires.
3. Calls the module's ``grains()`` for each resource and caches the
   returned dict.
4. Reports the full set of ``(type, id, grains)`` triples back to the
   master via ``_register_resources_with_master``.

Per-type loader
---------------

When a publish arrives that targets a managed resource, the minion
selects (or builds) a *per-resource execution loader* keyed by the
resource type. This loader is constructed exactly like the standard
minion loader, except:

* Loader dir search order is rewritten so that
  ``salt/resources/<rtype>/modules/`` (and the equivalent path inside
  any Salt extension that ships a resource type) sits **ahead of** the
  standard ``salt/modules/``. A file at the per-type path wins its
  slot; standard modules fill any slot the resource type doesn't
  override. See :func:`salt.loader._module_dirs`.
* A few dunders are packed specifically for resource context.
  ``__grains__`` is the resource's grain dict (not the managing
  minion's). ``__resource__`` is ``{"type": ..., "id": ...}``.
  ``__minion__`` is the managing minion's regular execution-module
  loader, available as an explicit escape hatch when a resource module
  needs to reach back to the host. See
  :ref:`resources-state-authoring`.

The state loader (``salt.loader.states``) is built the same way: it
discovers state modules from per-type ``states/`` directories first,
then falls back to ``salt/states/``.


Dispatch: how a publish becomes a resource job
==============================================

This is the path a publish takes from the master's wire to a return.

1. **Master publishes**. ``CkMinions`` produces a wait list combining
   per-minion matches with per-resource matches read from the
   ``resource_grains`` bank and the SRN registry. For ``T@ssh:web-01``
   the wait list is ``{"web-01"}``; for ``state.apply`` against
   ``T@ssh:web-01`` it is ``{<managing-minion-id>}`` (the merge-mode
   remap — see :ref:`resources-arch-merge`).
2. **Minion accepts the load**.
   :meth:`~salt.minion.Minion._target_load` runs
   :meth:`~salt.minion.Minion._resolve_resource_targets` against the
   target expression. The result is a list of
   ``{"type": ..., "id": ...}`` dicts.
3. **Minion fans out**. For non-merge functions the minion calls
   :meth:`~salt.minion.Minion._handle_decoded_payload` once per matched
   resource, copying the load and setting ``load["resource_target"]``
   to that resource. Each copy runs in its own subprocess like any
   other job.
4. **The job picks the per-resource loader**.
   :meth:`~salt.minion.Minion._thread_return` reads
   ``data["resource_target"]`` and selects the corresponding
   :py:attr:`~salt.minion.Minion.resource_loaders` entry. The function
   is executed against that loader, so ``__salt__["cmd.run"]`` (etc.)
   dispatches to per-resource overrides when they exist and to
   standard Salt modules otherwise.
5. **Return**. The result is published to the master with
   ``ret["resource_id"]`` set; the master's ``_return`` handler
   remaps ``load["id"] = load["resource_id"]`` so the CLI sees a return
   keyed by the resource id.

Special function classes
------------------------

Two sets of functions are treated specially:

:py:attr:`~salt.minion.Minion._NO_RESOURCE_FUNS`
   Internal minion housekeeping (job-status queries, module reloads,
   ``saltutil.sync_*``, …). Never dispatched to resources — they
   always run on the managing minion alone.

.. _resources-arch-merge:

:py:attr:`~salt.minion.Minion._MERGE_RESOURCE_FUNS`
   ``state.apply``, ``state.highstate``, ``state.sls``,
   ``state.sls_id``, ``state.single``. The managing minion runs the
   per-resource state apply *inline* and folds each resource's state
   IDs into a single response, prefixed with the resource id. The
   master's wait list contains the managing minion's id, not the
   resource ids; one combined block goes back to the operator. See
   :ref:`resources-state-authoring` for the prefixing rules and the
   ``__minion__`` escape hatch.


Per-type directory layout
=========================

A resource type is a Python package whose tree mirrors Salt's own
loader trees. Every directory is optional except ``__init__.py``:

.. code-block:: text

   salt/resources/<rtype>/
       __init__.py        # connection module — init, grains, helpers
       modules/           # execution-module overrides (filename = slot)
           cmd.py
           pkg.py
           state.py
           ...
       states/            # state-module overrides (filename = slot)
           ...
       grains/            # grain modules (per-resource grains, optional)
           ...

Salt extensions follow the same layout under their package path —
e.g. ``saltext/<ext>/resources/<rtype>/modules/<slot>.py`` — and Salt's
loader picks them up automatically via setuptools entry-point
discovery.

For an authoring guide see :ref:`resources-authoring`.


Why directory order instead of ``__virtual__``?
-----------------------------------------------

Earlier iterations of this design used ``__virtualname__`` collisions
and ``__virtual__`` guards keyed on ``opts["resource_type"]`` to decide
which module won a slot. That approach had two failure modes:

* It was easy for the *override* to opt **out** correctly while the
  *standard* module was unaware of the resource context, leaving the
  slot empty in the per-resource loader (the original "Gap 4" / "Gap 5"
  bug class).
* It coupled every standard module to the resource framework — any new
  resource type required edits to ``salt/modules/state.py``,
  ``salt/modules/cmd.py``, etc.

The directory-order approach inverts that. Standard modules know
nothing about resources. The loader picks the per-type version when
one exists and the standard version otherwise. Adding a resource type
requires no edits to core Salt — drop a directory in your extension
and you're done.


Cross-references
================

* Targeting reference: :ref:`resources-targeting`
* State authoring (merge mode, ``__minion__``): :ref:`resources-state-authoring`
* Operator commands: :ref:`resources-operations`
* Configuration options: :ref:`resources-configuration`
* Registry API: :py:mod:`salt.utils.resource_registry`
