.. _resources:

==============
Salt Resources
==============

.. versionadded:: 3008.0

A *Salt resource* is something a minion manages on behalf of the master —
an SSH host, a virtual appliance, an external API endpoint, a cloud
account, a CI/CD pipeline — addressed by an id of the operator's
choosing. Resources let Salt drive things that can't (or shouldn't) run
a minion of their own, without giving up Salt's targeting, state, and
return-handling machinery.

If you've used proxy minions, the conceptual leap is small: a resource is
the "thing being proxied for" expressed as a *first-class targeting
primitive* rather than a separate daemon. One Salt minion can manage
many resources of many types, each addressable individually.


Why resources?
==============

The same problem keeps coming back: you need Salt's primitives —
targeting, states, pillar, returners — pointed at a thing that isn't a
Salt minion.

* A pool of SSH-only hosts where you can't (or don't want to) install a
  minion: routers, switches, jump hosts, locked-down appliances.
* A SaaS or cloud control plane where the "node" is an API endpoint
  rather than a process: cloud accounts, Kubernetes clusters, Vault
  instances, container registries.
* A short-lived environment that appears and vanishes as a side effect
  of another state's success: ephemeral CI sandboxes, on-demand jump
  hosts (see :ref:`resources-derived`).

You could solve each of those with custom execution modules, with
``salt-ssh`` orchestration, with a proxy minion per thing, or with a
runner that wraps the call. Resources unify them: one targeting
expression, one return shape, one state-apply path, regardless of which
flavour of "remote thing" the operator is talking to.


When to reach for a resource (and when not to)
==============================================

A resource is the right tool when *all* of these are true:

* The thing has a stable identity an operator might want to address.
* You want to run Salt states or execution functions *against* it.
* You don't want to install a minion on it (or you can't).

A resource is **not** the right tool when:

* The thing already runs a Salt minion — just target the minion.
* You only need to read data once and act on the result locally — write
  a runner or an execution module.
* The thing is a configuration setting on the *minion itself* (a file,
  a service, a package) — that's already covered by the minion's normal
  state tree.


Comparison with proxy minions and salt-ssh
==========================================

.. list-table::
   :header-rows: 1
   :widths: 25 25 25 25

   * - Aspect
     - Proxy minion
     - ``salt-ssh``
     - Salt resource
   * - Process model
     - One daemon per target
     - Master-driven, no daemon
     - One managing minion per N resources
   * - Targeting
     - By proxy id (a minion)
     - By roster entry
     - By resource id or type
       (``T@<type>[:<id>]``)
   * - State engine
     - Local on the proxy
     - Master-driven
     - On the managing minion,
       merged into one return
   * - Pillar
     - Per proxy
     - Master's pillar
     - Per-resource subtree under
       :conf_minion:`resource_pillar_key`
   * - Best for
     - Network gear with a
       persistent control plane
     - Bootstrap, one-offs,
       agentless tasks
     - Fleets of remote things
       managed alongside their
       host minion

A managing minion can also manage resources whose *transport* is
salt-ssh — the SSH resource type ships with Salt — so the choice isn't
exclusive. Resources give you the targeting and state primitives;
salt-ssh remains a perfectly good transport.


Mental model
============

* The **master** holds the system-of-record for which minion owns which
  resource (the :ref:`resource registry <resources-architecture>`).
  Targeting matchers (``T@``, ``G@``, ``L@``, wildcard globs, …)
  consult that registry to expand expressions like ``T@ssh`` or
  ``salt '*'`` into the union of minions and resources.
* The **managing minion** carries per-resource grain dicts, a
  per-resource loader, and the connection plumbing. When a publish
  arrives for ``T@ssh:web-01`` the managing minion dispatches the job
  to the resource loader and returns a result keyed by ``web-01``.
* The **resource type** is just a Python package under
  ``salt/resources/<type>/`` (or under any Salt extension's
  ``saltext/<ext>/resources/<type>/``). Its layout mirrors Salt's own
  loader trees: ``modules/``, ``states/``, ``grains/`` — except the
  files inside are *overrides* that win their slot when running in
  that resource's context, and standard Salt modules fill the rest.


Documentation map
=================

If you're new to resources, read :ref:`resources-tutorial` first — it
takes the bundled ``dummy`` type from scratch to a working
``salt -C 'T@dummy' state.apply`` in about ten minutes. From there:

.. toctree::
   :maxdepth: 1

   tutorial
   architecture
   targeting
   state_authoring
   derived
   operations
   configuration
   authoring/index

API reference (autodoc):

.. toctree::
   :maxdepth: 1

   /ref/resources/index
