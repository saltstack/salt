.. _asyncio_sync_boundary:

Proposal: the synchronous boundary for asyncio
==============================================

This is the Step 2 design proposal for `issue #70366
<https://github.com/saltstack/salt/issues/70366>`_. It describes the contract
to review before replacing ``salt.utils.asynchronous.SyncWrapper`` in 3009.
These are proposed migration rules, rather than guarantees of the current
implementation. Acceptance of the proposal and implementation are separate
steps.

``SyncWrapper`` currently creates an event loop for each wrapped object.
Its callers include request channels, event subscribers and publishers,
and the Tornado HTTP backend. Moving those objects to one background loop
also changes thread ownership, callbacks, cancellation and shutdown. A
replacement therefore needs a defined boundary before callers migrate.

APIs on each side
-----------------

Keep the established blocking entry points for CLI commands, execution
modules and synchronous integrations. Behind each entry point, the
transport work is asynchronous and runs on its owning loop.

.. list-table:: Proposed API boundary
   :header-rows: 1
   :widths: 28 40 32

   * - Blocking entry point
     - Path for asynchronous callers
     - Resource owner
   * - ``LocalClient.cmd()``, ``cmd_iter()`` and ``cmd_async()``
     - Use the existing ``run_job_async()`` and ``pub_async()`` where
       applicable; provide an asynchronous return iterator before migrating
       callers that collect job returns.
     - ``LocalClient`` owns its event subscriptions and loaders; retain
       ``destroy()`` and its context manager.
   * - ``ReqChannel.factory()`` and the resulting channel methods
     - ``AsyncReqChannel.factory()`` on the caller's loop, followed by
       awaited channel methods.
     - The channel owns its transport. The synchronous facade closes it on
       the bridge; async callers use ``close_async()`` or ``async with``.
   * - ``SaltEvent.get_event()`` and ``fire_event()``
     - A loop-owned event subscription and awaited ``fire_event_async()``;
       migrate callback users without blocking their loop.
     - The event handle owns its subscriber, pusher and publish tasks.
       Retain ``destroy()`` for synchronous handles; add awaited cleanup
       for asynchronous handles.
   * - File client methods
     - An asynchronous file-client path, introduced with its callers.
     - The file client closes channels it created, without closing borrowed
       channels or a caller's loop.
   * - ``salt.utils.http.query()``
     - An explicit asynchronous HTTP entry point, introduced separately.
     - The request or an explicitly managed client pool owns the HTTP
       client. Retain the existing backend choice during this migration.

``LocalClient.cmd_async()`` submits a remote job and returns its job ID;
despite its name, it is a normal synchronous Python method. It must not be
treated as a coroutine API.

Do not change an existing method's return type depending on whether an
event loop happens to be running. An async transport must never call back
through a blocking facade to reach another async transport.

Loop ownership and dispatch
---------------------------

Provide one lazily started bridge per process for synchronous callers.
The bridge owns an asyncio loop and its background thread. Native async
callers continue to use their existing loop; they do not need a background
bridge. Thus, one bridge per process does not mean one loop for all Salt
code in that process.

The synchronous path is::

    synchronous caller -> bridge submission -> async channel / transport
                       <- result or exception <- owning event loop

The asynchronous path awaits the channel or transport directly on the
caller's loop. Objects created on one path cannot be reused on the other.
Sharing authentication data must not share loop-bound auth tasks, futures
or sockets between those paths.

Construct loop-bound objects on their owning loop. Run every operation
that touches their sockets, tasks or mutable transport state there too,
including methods declared with ordinary ``def``, such as ``close()``.
Passing through non-coroutine methods to the caller's thread is unsafe.
Expose returned data or explicit facade operations, rather than the raw
wrapped object or its mutable attributes.

A call submitted to the bridge carries the caller's context variables.
Subsequent calls must not inherit another caller's rendering, tracing or
authentication context. Copy or transfer mutable inputs according to the
API's ownership contract; scheduling an object on another thread does not
make its dictionaries thread-safe.

Blocking on the bridge from its own thread raises ``RuntimeError`` before
submitting work. Blocking facades are also unsuitable inside another
running event loop: migrate those callers to an async entry point before
enforcing a running-loop guard at that facade. This restriction needs an
explicit compatibility review for each migrated API. Do not transparently
create another thread or loop to handle nested calls.

Tornado's ``IOLoop`` may remain an adapter on the same asyncio loop while
transports migrate. Removing ``aioloop()`` and ``current_ioloop()`` comes
after their callers accept asyncio loops. This proposal does not require
rewriting ``rest_tornado`` or changing HTTP libraries.

Timeouts, results and callbacks
-------------------------------

Preserve each public API's timeout units, retry policy and explicit
unbounded waits. For example, ``fire_event()`` uses milliseconds while
channel timeouts use seconds. A bridge wait must not silently add an
unlimited wait after an operation with a finite deadline. Carry the
operation's remaining budget through submission and execution; define
the total budget from the API's existing per-attempt timeout and retries.

Return the operation's result or propagate its exception. On a caller
timeout or interruption, request cancellation on the owning loop and
observe its completion or report that cleanup exceeded its separate
shutdown budget. Cancelling a wait cannot undo a request that was already
sent to a master, so a timeout must not imply that the remote operation
did not run.

Pending receives and read tasks can be intentional parts of a live
connection. Their owner tracks and closes them explicitly. Do not infer
task ownership from garbage-collector referrers, or cancel all tasks on
the shared loop when one request finishes.

Event migration must distinguish scheduling a publish, completing the
local send, and delivery to a consumer. Keep the existing return contract
of each entry point until a separately reviewed change defines otherwise.
In particular, the current ``fire_event()`` can return ``True`` after
scheduling a publish on an externally supplied loop. Awaited
``fire_event_async()`` is the path for waiting for that local publish.
Neither result is an acknowledgement from an event consumer.

Audit callback thread ownership before migrating event and HTTP users.
HTTP streaming and header callbacks require preserved ordering,
backpressure and exception handling. A synchronous caller's file handle
or callback cannot silently move to the bridge thread. These cases are a
gate for the HTTP migration, not part of the first channel pilot.

Closing objects and stopping the process
----------------------------------------

Separate object lifetime from bridge lifetime:

* The creator closes the channel, file client, event handle or HTTP client
  it owns. Keep established ``close()`` and ``destroy()`` names on
  synchronous APIs and make repeated cleanup harmless. Prefer their
  context managers for bounded uses.
* Async cleanup is awaited on the owning loop. For request channels,
  use the existing ``close_async()`` and async context manager. Drain the
  send/receive task before releasing its ZeroMQ sockets and context.
* Closing an object cancels and awaits that object's tasks. It does not
  stop the shared loop, close another object's resources or shut down a
  caller-supplied loop.
* Once closing begins, reject new operations on that handle. Serialize
  cleanup with in-flight calls so that a late callback cannot recreate
  resources after close returns.
* Construction failure cleans up resources allocated before the failure,
  even if no facade was returned to the caller.
* The process or daemon lifecycle owns bridge shutdown. It rejects new
  submissions, closes registered live owners, cancels and awaits remaining
  bridge tasks, shuts down async generators and the default executor,
  then stops the loop and joins its thread.

Bridge startup and shutdown need explicit finite budgets. Startup failure
must wake callers, and calls after shutdown must fail rather than start a
new bridge during interpreter teardown. Tests need an explicit reset
between independently owned lifecycles in the same process.
If the loop thread exits unexpectedly, fail pending and new submissions
instead of letting their synchronous callers wait indefinitely.

Cancellation is cooperative. A shutdown deadline can report stuck work;
it cannot safely kill a Python thread or guarantee that arbitrary executor
work has ended. Do not report successful cleanup by closing a loop with
live tasks or by leaving an unbounded thread join in a finalizer.

For migrated 3009 objects, ``__del__`` may warn about an unclosed resource
but must not run asynchronous cleanup, wait for another thread or terminate
a native context. Remove existing cleanup fallbacks only after the owning
callers have explicit cleanup and tests. Coordinate this with `PR #70122
<https://github.com/saltstack/salt/pull/70122>`_; the ``3008.x`` safety nets
from `PR #70261 <https://github.com/saltstack/salt/pull/70261>`_ remain a
separate compatibility decision.

Fork and process creation
-------------------------

Start the bridge lazily after the relevant worker process exists. Record
the creating PID on both the bridge and its resource handles. After a
fork, reset the child's bridge registry and synchronization primitives;
the parent's background thread does not exist in the child.

An inherited handle must reject operations and cleanup in the child.
Create a fresh client there instead of invoking transport cleanup on an
inherited native context or attempting to drive the parent's copied loop.
The fork implementation must account for transport finalizers as well as
the bridge registry. Verify parent and child independently; PID checks on
method calls alone do not prevent inherited finalizers from running.

On platforms using process spawning, initialize the bridge in the new
interpreter. No thread, loop or connection is created merely by importing
the helper.

Implementation and review gates
-------------------------------

Use separate PRs for these changes, with no global ``SyncWrapper`` alias
replacement:

1. Review this API boundary, the running-loop restriction, ownership rules
   and lifecycle budgets. Record the accepted decisions in issue #70366.
2. Add the bridge and lifecycle tests without redirecting production
   callers. Require startup failure, concurrent submissions, context
   isolation, cancellation, repeated shutdown and fork coverage.
3. Pilot a short-lived request-channel caller such as
   ``status.ping_master()`` behind a separate factory. Test ZeroMQ and TCP
   authentication, errors and close ordering before changing the default
   ``ReqChannel.factory()`` implementation.
4. Migrate remaining channel and file-client owners in small groups. Audit
   auth caches and all existing running-loop callers as part of this work.
5. Migrate HTTP after its callback contract is verified. Migrate the event
   bus and TCP publisher with nested-publish, reconnect, fork and shutdown
   stress tests. Async publishing must reach the async publisher directly.
6. Remove unused loop adapters, ``SyncWrapper`` and its cleanup fallbacks
   after the corresponding callers and tests have migrated.

The acceptance tests must show that closing one client leaves another
usable, repeated calls do not accumulate loops, threads, tasks or file
descriptors, and concurrent or nested operations cannot block the owning
loop. Exercise interruption during authentication, receive, publish and
close, including a master outage. Include Linux fork and Windows spawn
coverage; a skipped macOS fork test is not a substitute for Linux coverage.

A shared-loop prototype needs these lifecycle, ownership and compatibility
guarantees before it becomes a replacement. Step 2 is complete only when
the proposed contracts have been reviewed; publishing this document alone
does not record agreement.
