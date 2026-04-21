.. _tunable-worker-pools:

====================
Tunable Worker Pools
====================

.. versionadded:: 3008.0

The Salt Master dispatches every minion and API request to an ``MWorker``
process.  Historically all workers belong to a single pool sized by
:conf_master:`worker_threads`, which means a single slow or expensive command
can occupy every worker and delay time-critical work such as authentication or
job publication.

Tunable worker pools let you partition the master's MWorkers into any number
of named pools and route specific commands to specific pools.  This gives you
transport-agnostic, in-master Quality of Service without running a separate
master per workload.


When to use worker pools
========================

Worker pools solve problems that surface as minion *starvation* or
authentication timeouts under load:

* A handful of minions run long state applies that hold MWorkers for minutes at
  a time, blocking every other minion's returns and ``_auth`` requests behind
  them.
* Runner or wheel calls issued from an orchestration engine or the salt-api
  compete for workers with minion traffic.
* A noisy subset of minions (heavy returners, peer publish, beacons) needs to
  be isolated so it can't crowd out the rest of the fleet.

When pools are enabled, incoming requests are classified by their ``cmd``
field and dispatched to the pool that owns that command.  Each pool has its
own IPC RequestServer and its own MWorker processes, so work in one pool
cannot block work in another.

Pools are a drop-in replacement for :conf_master:`worker_threads`.  A master
with the default configuration uses a single "default" pool with five workers
and a catchall of ``*`` — byte-for-byte equivalent to the legacy
single-pool behavior.


Quick start
===========

The default configuration requires no changes and matches the legacy behavior
exactly.  To carve a dedicated pool off for authentication, for example, add
the following to ``/etc/salt/master``:

.. code-block:: yaml

    worker_pools:
      auth:
        worker_count: 2
        commands:
          - _auth
      default:
        worker_count: 5
        commands:
          - "*"

With that configuration the master starts two pools:

* ``auth`` — two MWorkers that only ever handle ``_auth`` requests.
* ``default`` — five MWorkers that handle every other command (thanks to the
  catchall ``*``).

Because ``_auth`` now has a dedicated pool it can never be starved by
long-running ``_return`` or ``_minion_event`` traffic in the default pool.


Configuration reference
=======================

Worker pools are controlled by two master options:

* :conf_master:`worker_pools_enabled`
* :conf_master:`worker_pools`

See :ref:`the master configuration reference <configuration-salt-master>` for
the authoritative description of each option.

Per-pool settings
-----------------

Each entry under ``worker_pools`` is a pool definition with the following
keys:

``worker_count`` (integer, required)
    The number of MWorker processes to start for the pool.  Must be ``>= 1``.

``commands`` (list of strings, required)
    The commands routed to this pool.  Each entry is matched against the
    ``cmd`` field of the incoming payload.

    * An exact string (for example ``_auth`` or ``_return``) matches a single
      command.
    * A single ``"*"`` entry makes the pool a *catchall* that receives every
      command no other pool has claimed.

    A command must be mapped to at most one pool.  Exactly one pool must use
    the ``"*"`` catchall entry so every command has a routing destination.

The catchall pool
-----------------

Every configuration must have a fallback for commands that are not
explicitly mapped.  Designate one pool as the catchall by giving it
``commands: ["*"]`` (or by including ``"*"`` alongside explicit commands).

The master refuses to start if no pool provides a catchall, or if multiple
pools declare one.

Backward compatibility with ``worker_threads``
----------------------------------------------

If ``worker_pools`` is *not* set but :conf_master:`worker_threads` is, the
master automatically builds a single catchall pool with
``worker_count == worker_threads``.  Existing configurations therefore keep
working without any changes.

To disable pooling entirely and use the old single-queue MWorker model, set
``worker_pools_enabled: False``.  This is primarily useful for debugging or
for transports that do not yet support pooled routing natively.


Worked examples
===============

Isolate authentication
----------------------

The most common use case: guarantee ``_auth`` is never blocked behind slow
minion returns.

.. code-block:: yaml

    worker_pools:
      auth:
        worker_count: 2
        commands:
          - _auth
      default:
        worker_count: 8
        commands:
          - "*"

Separate minion returns, peer publish, and the rest
---------------------------------------------------

Large deployments frequently want to isolate high-volume return traffic from
the authentication and publish paths:

.. code-block:: yaml

    worker_pools:
      auth:
        worker_count: 2
        commands:
          - _auth
      returns:
        worker_count: 10
        commands:
          - _return
          - _syndic_return
      peer:
        worker_count: 4
        commands:
          - _minion_event
          - _master_tops
      default:
        worker_count: 4
        commands:
          - "*"


Architecture
============

When :conf_master:`worker_pools_enabled` is ``True`` (the default) the master
wraps its external transport in a ``PoolRoutingChannel``:

.. code-block:: text

    External transport (4506)
            │
            ▼
    PoolRoutingChannel
            │  route by payload['load']['cmd']
            ▼
    Per-pool IPC RequestServer  ─► MWorker-<pool>-0
                                 ─► MWorker-<pool>-1
                                 ─► ...

The routing channel inspects the ``cmd`` field of each incoming request
(decrypting first where required) and forwards the original payload over an
IPC channel to the target pool's RequestServer, which in turn dispatches it
to one of its MWorkers.  Each pool has its own IPC socket (or TCP port in
``ipc_mode: tcp`` deployments), so backpressure and workload in one pool
stays local to that pool.

Because routing is performed inside the routing process and the payload is
forwarded intact, the pool decision is made without modifying transports.
ZeroMQ, TCP, and WebSocket masters all benefit equally.

MWorker naming
--------------

When pools are active, MWorker process titles include their pool name and
index, for example ``MWorker-auth-0`` or ``MWorker-default-3``.  This makes
per-pool resource usage easy to inspect with ``ps``, ``top``, or Salt's own
process metrics.

Authentication execution path
-----------------------------

``_auth`` is executed in exactly one place regardless of whether pooling is
enabled:

* With pools enabled, ``_auth`` is routed like any other command to the pool
  that owns it (or the catchall).  The worker in that pool invokes
  ``salt.master.ClearFuncs._auth`` directly.
* With pools disabled, the plain request server channel intercepts ``_auth``
  inline before any payload reaches a worker and handles it in-process.

The two code paths are mutually exclusive.  See the class docstrings on
``salt.channel.server.ReqServerChannel`` and
``salt.channel.server.PoolRoutingChannel`` for the full rationale.


Sizing guidance
===============

Worker pools shift the sizing question from "how many MWorkers in total" to
"how many MWorkers per workload".  As a starting point:

* Sum of ``worker_count`` across all pools should stay within about 1.5× the
  available CPU cores, matching the historical
  :conf_master:`worker_threads` guidance.
* Reserve a small, dedicated pool for ``_auth`` (2 workers is usually enough)
  whenever you have workloads that can stall a pool for more than a few
  seconds.
* Size the return/peer pools based on steady-state minion traffic.  As a
  rough rule of thumb, start with one worker per 200 actively returning
  minions and adjust based on observed queue depth.
* Keep a catchall or explicit default pool big enough to absorb the
  background noise of runners, wheels, and miscellaneous commands.


Validation and failure modes
============================

The master validates the pool configuration at startup and refuses to run if
any of the following are true:

* ``worker_pools`` is not a dictionary or is empty.
* A pool name is not a string, is empty, contains a path separator
  (``/`` or ``\``), begins with ``..``, or contains a null byte.
* A pool is missing ``worker_count`` or the value is not an integer ``>= 1``.
* A pool's ``commands`` field is missing, not a list, or empty.
* The same command is claimed by more than one pool.
* No pool, or more than one pool, uses the ``"*"`` catchall entry.

Errors are reported with a consolidated message listing every problem the
validator found, making it straightforward to fix the configuration in a
single pass.


Observability
=============

Every routing decision is counted per-pool inside the master.  The pool name
is also embedded in the MWorker process title, so standard process
inspection tools give you a clear view of per-pool CPU and memory usage.

Routing log lines are emitted at ``INFO`` level when pools come up and at
``DEBUG`` level for each routing decision.  Enable debug logging on the
master if you need to trace which pool handled a specific request.
