.. _tracing:

===================================
Distributed Tracing (OpenTelemetry)
===================================

Salt can emit OpenTelemetry spans for every inter-process hop, so a single
job (``salt '*' test.ping``) becomes a single distributed trace that crosses
the CLI, the master, the minion, the return path, and any reactor or syndic
forwarding in between.

The implementation uses standard W3C TraceContext (``traceparent`` /
``tracestate``) for propagation and ships spans through an OTLP exporter.
Jaeger ingests OTLP natively, as do most modern tracing backends
(Tempo, Honeycomb, Datadog OTLP, etc.).

Trace context propagates **inside** the AES-encrypted Salt envelope: an
attacker on the wire cannot see the trace headers, and authenticated
participants (master / minion / syndic) decode them after AES decryption.

Tracing is **disabled by default** and is a complete no-op when not
configured.  No spans are created, no exporter is initialised, and no
background threads are started.

Configuration
-------------

Add a ``tracing`` block to the master and minion configs.  The block is
identical on both daemons, and applies to ``salt-cli``, ``salt-call``,
``salt-api`` and ``salt-ssh`` as well.

.. code-block:: yaml

    tracing:
      enabled: true
      exporter: otlp-http            # otlp-http | otlp-grpc | console
      endpoint: ""                   # OTel SDK default endpoint when empty
      service_name: ""               # auto-derived when empty
      sampler: parent_based          # parent_based | always_on | always_off | trace_id_ratio
      sampler_arg: 1.0
      resource_attributes: {}
      insecure: true                 # gRPC TLS disabled (ignored for HTTP)
      headers: {}                    # OTLP authentication headers

``enabled``
    Master switch.  When ``false`` (the default), everything in this module
    is a no-op.

``exporter``
    ``otlp-http`` (default) sends spans via HTTP/protobuf to ``endpoint``.
    Pure-Python; ships in salt's base requirements; works on every
    interpreter.
    ``otlp-grpc`` sends via gRPC.  Requires
    ``opentelemetry-exporter-otlp-proto-grpc`` to be installed separately
    (it pulls in ``grpcio``, which lacks prebuilt wheels for some
    platform / interpreter combinations).
    ``console`` prints spans to stdout for debugging.

``endpoint``
    OTLP collector URL.  When empty, the OTel SDK default is used
    (``http://localhost:4318/v1/traces`` for HTTP,
    ``http://localhost:4317`` for gRPC).

``service_name``
    The ``service.name`` resource attribute.  When empty, Salt fills this in
    automatically: ``salt-master``, ``salt-minion-<id>``, ``salt-cli``,
    ``salt-call``, ``salt-api``.

``sampler``
    Which sampler to install on the ``TracerProvider``.

    - ``parent_based`` (default): follow the parent's sample decision; root
      spans are sampled.  Use ``sampler_arg`` < 1.0 to apply a ratio to
      root spans.
    - ``always_on``: sample every span.
    - ``always_off``: drop every span (testing only).
    - ``trace_id_ratio``: sample ``sampler_arg`` fraction of trace IDs.

``resource_attributes``
    Extra attributes merged into the OTel Resource (e.g. ``deployment.environment: prod``).

``insecure``
    Disable gRPC TLS to the collector.  Ignored for the HTTP exporter.

``headers``
    Additional headers sent on every OTLP request, e.g.
    ``Authorization: Bearer <token>`` for a hosted collector.

Hops covered
------------

A single ``salt '*' test.ping`` produces a trace spanning at least:

1. ``salt.cli.test.ping`` — root span on the CLI.
2. ``salt.req.send.publish`` — CLI → master request.
3. ``salt.req.recv.publish`` — master receives the request.
4. ``salt.pub.send`` — master publishes the job.
5. ``salt.minion.recv.test.ping`` — minion receives the published command.
6. ``salt.minion.exec.test.ping`` — minion executes the function.
7. ``salt.req.send._return`` — minion returns to master.
8. ``salt.req.recv._return`` — master receives the return.

Other instrumented hops:

- Event bus (``fire_event`` / ``get_event``) — every IPC and TCP-IPC event
  carries trace context in its data dict.
- Reactor — extracts trace context from incoming events and parents the
  reaction span correctly.
- Syndic forwarding — both inbound (from upstream master) and outbound (to
  downstream minions).
- Salt-SSH — propagates trace context as the ``TRACEPARENT`` environment
  variable on the remote shim.
- Salt-API — extracts the ``traceparent`` HTTP header from incoming
  requests; webhooks inject context into the events they fire.

Running a quick demo
--------------------

Spin up an all-in-one Jaeger:

.. code-block:: bash

    docker run -d --name jaeger \
      -p 16686:16686 -p 4318:4318 \
      jaegertracing/all-in-one:latest

Configure master + minion with:

.. code-block:: yaml

    tracing:
      enabled: true
      exporter: otlp-http
      endpoint: http://localhost:4318/v1/traces
      sampler: always_on

Start them, run ``salt '*' test.ping``, then visit
``http://localhost:16686`` and search for the ``salt-cli`` service.  You
should see a single trace with spans hanging off three services:
``salt-cli``, ``salt-master`` and ``salt-minion-<id>``.

Fork handling
-------------

The OTel ``BatchSpanProcessor`` runs a background thread that does not
survive ``fork()``.  Salt rebuilds the provider in every forked child the
first time a tracing API is invoked, so worker processes spun up by the
master / minion get their own functioning exporter without any caller
action.  Unflushed spans queued by the parent at the instant of fork may
be lost; for short-lived spans this is rarely visible, but if you observe
gaps consider lowering ``BatchSpanProcessor`` queue intervals via the OTel
environment variables.

Payload overhead
----------------

When tracing is enabled and a recording span is active, every Salt request
and event grows by roughly 60 bytes (the W3C ``traceparent`` string).
When no recording span is active — for example, an internal periodic event
fired outside a request handler — no headers are added.
