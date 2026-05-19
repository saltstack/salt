.. _metrics:

================================
Metrics (OpenTelemetry)
================================

Salt can emit OpenTelemetry metrics — counters, histograms and
observable gauges — for the operational signals that operators most
often care about: job throughput, return latency, minion connectivity,
worker queue depth, file-descriptor pressure, and returner egress
health.

Metrics complement the :ref:`distributed tracing <tracing>` story.
Traces answer "what happened during one job?"; metrics answer "what's
happening across the fleet right now?".

The instrumentation is **disabled by default** and is a complete no-op
when not configured.  No exporter is initialised, no background threads
are started, no Prometheus listener is bound, and no payload changes
land on the wire.

Configuration
-------------

Add a ``metrics`` block to the master and minion configs.  Settings
are the same on both daemons.

.. code-block:: yaml

    metrics:
      enabled: true
      exporter: otlp-http             # otlp-http | otlp-grpc | prometheus | console
      endpoint: ""                    # OTLP collector URL (empty = SDK default)
      service_name: ""                # empty = auto-derived from process role
      resource_attributes: {}         # extra OTel Resource attributes
      insecure: true                  # gRPC TLS off (ignored for non-grpc)
      headers: {}                     # OTLP auth headers
      export_interval_seconds: 60     # PeriodicExportingMetricReader interval
      prometheus:
        host: 127.0.0.1               # localhost-bind by default
        port: 9464
      histogram_boundaries:
        salt.job.duration: [1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000, 60000]
        salt.minion.exec.duration: [1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000]
        salt.master.requests.duration: [1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000]

``enabled``
    Master switch.  ``false`` (the default) means everything in this
    module is a no-op.

``exporter``
    - ``otlp-http`` (default) — push OTLP protobuf over HTTP.
      Pure-Python; ships in salt's base requirements.
    - ``otlp-grpc`` — push OTLP over gRPC.  Requires
      ``opentelemetry-exporter-otlp-proto-grpc`` installed separately
      (it pulls in ``grpcio``, which lacks prebuilt wheels for some
      platform / interpreter combinations).
    - ``prometheus`` — bind a local ``/metrics`` HTTP endpoint that
      Prometheus can scrape.  Operators who already run Prometheus can
      skip the OTel Collector entirely.
    - ``console`` — print metrics to stdout for debugging.

``endpoint``
    OTLP collector URL when ``exporter`` is ``otlp-http`` or
    ``otlp-grpc``.  When empty, the OTel SDK default is used
    (``http://localhost:4318/v1/metrics`` for HTTP,
    ``http://localhost:4317`` for gRPC).

``service_name``
    The ``service.name`` resource attribute.  When empty, salt fills
    this in automatically: ``salt-master``, ``salt-minion-<id>``,
    ``salt-cli``, ``salt-call``, ``salt-api``.

``export_interval_seconds``
    How often the periodic exporter flushes to the collector.  Ignored
    for the Prometheus pull exporter (Prometheus controls cadence via
    its scrape interval).

``prometheus.host`` / ``prometheus.port``
    Where the Prometheus pull listener binds.  Defaults to
    localhost-only.  In a multi-process master only the parent binds
    this port; counters incremented inside MWorker children are not
    visible through the parent's ``/metrics`` (use the OTLP push
    exporter if you need worker-side counters in a Prometheus
    deployment with multiple workers).

``histogram_boundaries``
    Per-instrument explicit bucket boundaries.  The defaults span
    sub-millisecond to one minute for ``salt.job.duration`` and
    sub-millisecond to ten seconds for ``salt.minion.exec.duration``.

Instrument inventory
--------------------

Counters
~~~~~~~~

- ``salt.jobs.published{fun}`` — jobs published from master to minions.
- ``salt.jobs.completed{fun,success}`` — returns received from minions.
- ``salt.auth.attempts{result}`` — master auth attempts; ``result`` is
  one of ``success``, ``invalid_id``, ``max_minions``, ``rejected``,
  ``error``.
- ``salt.master.requests.handled{cmd}`` — every request dispatched by
  the master worker (clear-funcs + aes-funcs), labelled by the salt
  ``cmd`` name (``publish``, ``_auth``, ``_return``, ``_serve_file``,
  ``mine_get``, …).  This is the OTel mirror of the per-command runs
  counter that ``master_stats`` exposes via the event bus.
- ``salt.events.fired{tag_prefix}`` — events placed on the event bus,
  labelled by the first non-``salt`` segment of the tag.
- ``salt.returners.calls{returner,status}`` — minion-side returner
  invocations; ``status`` is ``ok``, ``missing``, or ``error``.

Histograms
~~~~~~~~~~

- ``salt.job.duration{fun}`` (ms) — CLI-to-master-return wall-clock per
  minion return.  Recorded by ``LocalClient.get_iter_returns`` on each
  return event.
- ``salt.minion.exec.duration{fun}`` (ms) — minion-side wall-clock for
  a single function execution (the same window the
  ``salt.minion.exec.<fun>`` trace span covers).
- ``salt.master.requests.duration{cmd}`` (ms) — per-command master
  worker dispatcher latency, recorded in ``MWorker._handle_clear`` and
  ``MWorker._handle_aes``.  Together with the matching
  ``salt.master.requests.handled`` counter this gives feature parity
  with the legacy ``master_stats`` per-command ``runs`` + ``mean``
  surface, but live in OTel instead of fired as periodic events.

Observable gauges
~~~~~~~~~~~~~~~~~

- ``salt.master.connected_minions.count`` — sourced from
  :func:`salt.utils.minions.CkMinions.connected_ids`.  Registered only
  in the master parent process to avoid worker over-count.
- ``salt.master.workers.queue.depth{pool}`` — MWorker payloads in
  flight, observed via a shared ``multiprocessing.Value`` that every
  worker increments on ``_handle_payload`` entry and decrements on
  exit.
- ``salt.process.open_fds`` (``{fd}``) — current file-descriptor count
  from ``psutil.Process().num_fds()``.  Registered separately in the
  master parent and in the minion process.  Returns no observations on
  Windows where ``num_fds`` is unavailable.

Label cardinality
-----------------

Every label above has a bounded domain — ``fun`` (the salt module
namespace), ``result`` and ``status`` (small enums), ``returner`` (the
configured returner names), ``pool`` (the configured worker pool
names), ``tag_prefix`` (a small set of event tag namespaces).  No
instrument uses ``minion_id``, ``jid``, or ``user`` as a label.
Operators adding their own instruments should follow the same
discipline — these belong as trace span attributes, not metric labels.

Running a quick demo
--------------------

OTLP / OpenTelemetry Collector::

    docker run -d --name otelcol \
      -p 4318:4318 \
      otel/opentelemetry-collector-contrib

Configure master + minion::

    metrics:
      enabled: true
      exporter: otlp-http
      endpoint: http://localhost:4318/v1/metrics
      export_interval_seconds: 10

Start them, run a few ``salt '*' test.ping``\ s, and watch the collector
logs for ``salt.jobs.published``, ``salt.job.duration`` and friends.

Prometheus pull::

    metrics:
      enabled: true
      exporter: prometheus
      prometheus:
        host: 127.0.0.1
        port: 9464

``curl -s http://127.0.0.1:9464/metrics | grep '^salt_'`` then shows
the salt-namespaced metrics.

Fork handling
-------------

Like the tracing SDK, the OTel ``PeriodicExportingMetricReader``
background thread does not survive ``fork()``.  Salt rebuilds the
provider in every forked child the first time a metrics API is invoked,
so master workers and minion executor processes each get their own
functioning reader without any caller action.

Observable gauges are registered exactly once — in the master parent for
master-side gauges, in the minion process for minion-side gauges — to
avoid forked-worker over-counting.

Payload and CPU overhead
------------------------

Metric increments are zero-allocation when metrics are disabled (every
public function short-circuits before touching the OTel SDK).  When
enabled, counter and histogram operations are sub-microsecond.  The
``PeriodicExportingMetricReader`` background thread wakes on
``export_interval_seconds`` (default 60s).  The Prometheus pull listener
binds a single local port and serves a few KiB of text per scrape.

No metric instrumentation changes the on-the-wire format of any salt
request, event, or return — they are purely local to each daemon's
process.
