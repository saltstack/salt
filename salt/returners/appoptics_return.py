"""Salt returner to return highstate stats to AppOptics Metrics

To enable this returner the minion will need the AppOptics Metrics
client importable on the Python path and the following
values configured in the minion or master config.

The AppOptics python client can be found at:

https://github.com/appoptics/python-appoptics-metrics

.. code-block:: yaml

    appoptics.api_token: abc12345def

An example configuration that returns the total number of successes
and failures for your salt highstate runs (the default) would look
like this:

.. code-block:: yaml

    return: appoptics
    appoptics.api_token: <token string here>


The returner publishes the following metrics to AppOptics:

- saltstack.failed
- saltstack.passed
- saltstack.retcode
- saltstack.runtime
- saltstack.total


You can add a tags section to specify which tags should be attached to
all metrics created by the returner.

.. code-block:: yaml

    appoptics.tags:
      host_hostname_alias: <the minion ID - matches @host>
      tier: <the tier/etc. of this node>
      cluster: <the cluster name, etc.>


If no tags are explicitly configured, then the tag key ``host_hostname_alias``
will be set, with the minion's ``id`` grain being the value.

In addition to the requested tags, for a highstate run each of these
will be tagged with the ``key:value`` of ``state_type: highstate``.

In order to return metrics for ``state.sls`` runs (distinct from highstates), you can
specify a list of state names to the key ``appoptics.sls_states`` like so:

.. code-block:: yaml

    appoptics.sls_states:
      - role_salt_master.netapi
      - role_redis.config
      - role_smarty.dummy


This will report success and failure counts on runs of the
``role_salt_master.netapi``, ``role_redis.config``, and
``role_smarty.dummy`` states in addition to highstates.

This will report the same metrics as above, but for these runs the
metrics will be tagged with ``state_type: sls`` and ``state_name`` set to
the name of the state that was invoked, e.g. ``role_salt_master.netapi``.

"""


import logging

import salt.returners
import salt.utils.jid

try:
    import appoptics_metrics

    HAS_APPOPTICS = True
except ImportError:
    HAS_APPOPTICS = False

# Define the module's Virtual Name
__virtualname__ = "appoptics"

log = logging.getLogger(__name__)


def __virtual__():
    if not HAS_APPOPTICS:
        return (
            False,
            "Could not import appoptics_metrics module; "
            "appoptics-metrics python client is not installed.",
        )
    return __virtualname__


def _get_options(ret=None):
    """
    Get the appoptics options from salt.
    """
    attrs = {
        "api_token": "api_token",
        "api_url": "api_url",
        "tags": "tags",
        "sls_states": "sls_states",
    }

    _options = salt.returners.get_returner_options(
        __virtualname__, ret, attrs, __salt__=__salt__, __opts__=__opts__
    )

    _options["api_url"] = _options.get("api_url", "api.appoptics.com")
    _options["sls_states"] = _options.get("sls_states", [])
    _options["tags"] = _options.get(
        "tags", {"host_hostname_alias": __salt__["grains.get"]("id")}
    )

    log.debug("Retrieved appoptics options: %s", _options)
    return _options


def _get_appoptics(options):
    """
    Return an appoptics connection object.
    """
    conn = appoptics_metrics.connect(
        options.get("api_token"),
        sanitizer=appoptics_metrics.sanitize_metric_name,
        hostname=options.get("api_url"),
    )
    log.info("Connected to appoptics.")
    return conn


def _calculate_runtimes(states):
    results = {"runtime": 0.00, "num_failed_states": 0, "num_passed_states": 0}

    for state, resultset in states.items():
        if isinstance(resultset, dict) and "duration" in resultset:
            # Count the pass vs failures
            if resultset["result"]:
                results["num_passed_states"] += 1
            else:
                results["num_failed_states"] += 1

            # Count durations
            results["runtime"] += resultset["duration"]

    log.debug("Parsed state metrics: %s", results)
    return results


def _state_metrics(ret, options, tags):
    # Calculate the runtimes and number of failed states.
    stats = _calculate_runtimes(ret["return"])
    log.debug("Batching Metric retcode with %s", ret["retcode"])
    appoptics_conn = _get_appoptics(options)
    q = appoptics_conn.new_queue(tags=tags)

    q.add("saltstack.retcode", ret["retcode"])
    log.debug("Batching Metric num_failed_jobs with %s", stats["num_failed_states"])
    q.add("saltstack.failed", stats["num_failed_states"])

    log.debug("Batching Metric num_passed_states with %s", stats["num_passed_states"])
    q.add("saltstack.passed", stats["num_passed_states"])

    log.debug("Batching Metric runtime with %s".stats["runtime"])
    q.add("saltstack.runtime", stats["runtime"])

    log.debug(
        "Batching with Metric total states %s",
        stats["num_failed_states"] + stats["num_passed_states"],
    )
    q.add(
        "saltstack.highstate.total_states",
        (stats["num_failed_states"] + stats["num_passed_states"]),
    )
    log.info("Sending metrics to appoptics.")
    q.submit()


def returner(ret):
    """
    Parse the return data and return metrics to AppOptics.

    For each state that's provided in the configuration, return tagged metrics for
    the result of that state if it's present.
    """

    options = _get_options(ret)
    states_to_report = ["state.highstate"]
    if options.get("sls_states"):
        states_to_report.append("state.sls")
    if ret["fun"] in states_to_report:
        tags = options.get("tags", {}).copy()
        tags["state_type"] = ret["fun"]
        log.info("Tags for this run are %s", str(tags))
        matched_states = set(ret["fun_args"]).intersection(
            set(options.get("sls_states", []))
        )
        # What can I do if a run has multiple states that match?
        # In the mean time, find one matching state name and use it.
        if matched_states:
            tags["state_name"] = sorted(matched_states)[0]
            log.debug("Found returned data from %s.", tags["state_name"])
        _state_metrics(ret, options, tags)
