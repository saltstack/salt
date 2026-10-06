.. _resources-derived:

==================
Derived resources
==================

.. note::

   Derived resources are a **design pattern** — not a runtime feature
   shipped in 3008.0. The framework that *enables* the pattern (the
   per-type loader, merge-mode state apply, ``__minion__`` escape
   hatch) is in 3008.0; the registry and lifecycle helpers described
   below are documented here as a forward reference and to give
   extension authors a stable target to design against.

A **derived resource** is a resource whose configuration is only
knowable at runtime, as a consequence of another resource reaching a
desired state.


The problem
===========

Static resources — the ones declared in :ref:`pillar
<resources-authoring-pillar>` before Salt runs — work well when
connection details are known up-front. A Kubernetes cluster with a
fixed API endpoint, a router whose IP doesn't change: declare them
once, target them with ``T@``.

Some resources don't fit that mould. Consider:

* A short-lived sandbox environment whose IP/credentials only exist
  after the ``starting_state.deployed`` state succeeds.
* A jump host that comes up as part of provisioning another resource,
  with credentials that need to be fetched from the provisioning
  system's API.
* A container that's launched by another resource's state apply, then
  needs further configuration applied to it.

Today's workaround is a multi-step recipe: apply the upstream state,
manually fetch the derived connection info, write it into a second
pillar file, apply the downstream state. Each step is a separate
``state.apply``; there's no single command that owns the full desired
state.


The pattern
===========

A derived resource is registered into a shared per-run registry by
the *upstream* state function — after it confirms the upstream
resource is healthy and connection info is fetchable. Subsequent
states in the same apply (and future runs) target the derived
resource using the same ``T@<type>:<id>`` syntax as any static
resource. The lifecycle:

.. code-block:: text

    Run 1 — first apply
    ───────────────────
    starting_state.deployed("env-01")
      → environment reaches "succeeded"
      → fetches connection_info()
      → registers a derived resource:
          type: ssh_host
          id:   jumphost-env-01
          config:
            host:     10.20.30.40
            user:     worker
            password: …
            source:   starting_state/env-01    ← provenance

    ssh_host.state_applied("jumphost-env-01", mods="openvpn.init")
      → resource is in the registry → executes normally

    Run 2+ — idempotent re-apply
    ────────────────────────────
    starting_state.deployed("env-01")
      → already succeeded, no-op
      → re-registers derived resource (idempotent)

    ssh_host.state_applied(...)
      → normal execution against cached registration

A single ``state.apply`` drives the whole flow.


Registry scopes
===============

A derived-resource registry has two natural scopes:

In-run scope (``__context__``)
   Entries survive for the lifetime of a single ``state.apply``.
   Sufficient when downstream states only run inside the same apply
   that registers the resource. Lost on minion restart or pillar
   refresh.

Cross-run scope (cache file)
   Entries persist to JSON in ``cachedir`` (e.g.
   ``/var/cache/salt/minion/derived_resources.json``). Lets
   ``T@ssh_host:jumphost-*`` work in later ``salt -C`` invocations
   without re-running the upstream state. Cache is invalidated when
   the source resource's grains change — typically when its
   ``status`` grain transitions away from ``succeeded``.

A working implementation would expose, at minimum::

    salt.utils.derived_resources.register(
        opts,
        resource_type, resource_id, config,
        source_srn=None,
    )

    salt.utils.derived_resources.get(
        opts,
        resource_type, resource_id,
    )

    salt.utils.derived_resources.invalidate(
        opts,
        source_srn,
    )


Integration points
==================

For a resource type to support being *the source* or *the target* of a
derivation, two hooks need to know about the registry.

``discover(opts)``
   Should check both pillar and the derived registry::

       def discover(opts):
           static = list(
               salt.utils.resources.pillar_resources_tree(opts)
               .get("ssh_host", {})
               .keys()
           )
           derived = salt.utils.derived_resources.list_for_type(
               opts, "ssh_host"
           )
           return static + derived

``init`` *(or wherever per-resource config is fetched)*
   Should fall back to the registry when a resource id isn't in
   pillar::

       cfg = (
           salt.utils.resources.pillar_resources_tree(opts)
           .get("ssh_host", {})
           .get(resource_id)
           or salt.utils.derived_resources.get(
               opts, "ssh_host", resource_id
           )
       )
       if cfg is None:
           raise RuntimeError(f"ssh_host {resource_id!r} unknown")

The *registering* side is an upstream state module that calls
``salt.utils.derived_resources.register(...)`` after confirming the
upstream resource is healthy. Provenance is tracked via the
``source_srn`` argument so the cache can be invalidated when the
source resource's state changes.


Example SLS
===========

A single apply that provisions an environment, registers a derived
jump-host resource, configures OpenVPN on the jump host, and pulls
the resulting client config back:

.. code-block:: yaml

    ensure_environment:
      starting_state.deployed:
        - name: env-01
        - register_resources: true

    configure_jumphost_vpn:
      ssh_host.state_applied:
        - name: jumphost-env-01
        - mods: openvpn.init
        - require:
            - starting_state: ensure_environment

    fetch_client_config:
      ssh_host.fetch_file:
        - name: jumphost-env-01
        - remote_path: /etc/openvpn/client.ovpn
        - local_path: /root/env-01-vpn.ovpn
        - require:
            - ssh_host: configure_jumphost_vpn


Open questions
==============

Some pieces of the pattern aren't settled in 3008.0:

* **Cache invalidation granularity.** Per-SRN or per-grain-key? Only
  the ``status`` transition typically matters; finer granularity
  would avoid spurious invalidations on volatile grains.
* **Secret storage.** Derived resource configs often contain
  credentials. The cross-run cache file needs the same handling as
  any pillar secret: filesystem permissions, encryption at rest,
  audit logging.
* **Ordering inside a single apply.** State requisites
  (``require``, ``onchanges``) order *state chunks*. The framework
  needs to make sure a derived resource registered by a chunk early
  in the apply is visible to a chunk later in the same apply — the
  ``discover`` cache may need to be refreshed mid-apply.
* **Orchestration.** ``salt-run state.orchestrate`` is a better fit
  for multi-resource workflows that span minions. The registry API
  should work the same from inside orchestrate.

The :ref:`resources-architecture` page documents the runtime framework
the design above builds on. Track progress on the runtime helpers
under the ``derived-resources`` topic in the Salt issue tracker.
