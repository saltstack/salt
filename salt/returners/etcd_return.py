"""
Return data to an etcd server or cluster

.. versionchanged:: 3009.0

    Restored for the etcd v3 API after its removal in 3008.0. It uses
    :mod:`salt.utils.etcd_util`, so the etcd v2 API and the
    ``etcd.require_v2`` option are no longer supported. It also works as a
    ``master_job_cache`` now, and each minion return is stored as one key.

:depends: - etcd3gw

In order to return to an etcd server, a profile should be created in the master
configuration file:

.. code-block:: yaml

    my_etcd_config:
      etcd.host: 127.0.0.1
      etcd.port: 2379

It is technically possible to configure etcd without using a profile, but this
is not considered to be a best practice, especially when multiple etcd servers
or clusters are available.

.. code-block:: yaml

    etcd.host: 127.0.0.1
    etcd.port: 2379

The profile takes the other ``etcd.*`` options of :mod:`salt.utils.etcd_util`
as well, such as ``etcd.username``/``etcd.password`` and the TLS options.

Additionally, two more options must be specified in the top-level configuration
in order to use the etcd returner:

.. code-block:: yaml

    etcd.returner: my_etcd_config
    etcd.returner_root: /salt/return

The ``etcd.returner`` option specifies which configuration profile to use. The
``etcd.returner_root`` option specifies the path inside etcd to use as the root
of the returner system.

Once the etcd options are configured, the returner may be used:

CLI Example:

    salt '*' test.ping --return etcd

It can also be the master's job cache:

.. code-block:: yaml

    master_job_cache: etcd

You can also set a TTL (time to live) value for the returner, in seconds:

.. code-block:: yaml

    etcd.ttl: 5

Without ``etcd.ttl``, the master's ``clean_old_jobs`` maintenance removes jobs
older than ``keep_jobs_seconds`` when this returner is the ``master_job_cache``.

You may also specify different roles for read and write operations. First,
create the profiles as specified above. Then add:

.. code-block:: yaml

    etcd.returner_read_profile: my_etcd_read
    etcd.returner_write_profile: my_etcd_write

With a write profile, ``etcd.ttl`` is read from that profile.

The data is stored under the root as follows:

- ``minions/<minion id>``: the last job ID the minion returned for
- ``jobs/<jid>/<minion id>``: the minion's return (``return``, ``retcode``,
  ``success``, ``out``, ``fun``, ``fun_args``, when present)
- ``jobs/<jid>/.load.p``: the job's load
- ``jobs/<jid>/.minions.p``: the minions the job targeted
- ``jobs/<jid>/.endtime.p``: the job's end time, with
  ``job_cache_store_endtime``
- ``jobs/<jid>/.nocache.p``: set when the job was started with ``nocache``

Values are msgpack-encoded by default, which also stores binary return data.
With ``etcd.encode_values: False`` they are stored as JSON instead, which
cannot hold binary data.
"""

import datetime
import logging

import salt.utils.etcd_util
import salt.utils.jid
import salt.utils.job
import salt.utils.json
import salt.utils.minions

log = logging.getLogger(__name__)

__virtualname__ = "etcd"

_LOAD = ".load.p"
_MINIONS = ".minions.p"
_ENDTIME = ".endtime.p"
_NOCACHE = ".nocache.p"
_RETURN_FIELDS = ("return", "retcode", "success", "out", "fun", "fun_args")


def __virtual__():
    """
    Only return if etcd3gw is installed
    """
    if salt.utils.etcd_util.HAS_ETCD_V3:
        return __virtualname__
    return False, "Could not import etcd returner; etcd3gw is not installed."


def _get_conn(opts, profile=None):
    """
    Establish a connection to etcd
    """
    if profile is None:
        profile = opts.get("etcd.returner")
    path = opts.get("etcd.returner_root", "/salt/return").rstrip("/")
    return salt.utils.etcd_util.get_conn(opts, profile), path


def _write_conn():
    """
    Return the write connection, the root path and the TTL to write with
    """
    write_profile = __opts__.get("etcd.returner_write_profile")
    if write_profile:
        ttl = __opts__.get(write_profile, {}).get("etcd.ttl")
    else:
        ttl = __opts__.get("etcd.ttl")
    client, path = _get_conn(__opts__, write_profile)
    return client, path, ttl


def _read_conn():
    return _get_conn(__opts__, __opts__.get("etcd.returner_read_profile"))


def _dump(client, value):
    # etcd_util msgpack-encodes values unless etcd.encode_values is off, and
    # then only strings can be stored.
    return value if client.encode_values else salt.utils.json.dumps(value)


def _load(client, value):
    if value is None or client.encode_values:
        return value
    return salt.utils.json.loads(value)


def _get(client, key):
    return _load(client, client.get(key))


def _set(client, key, value, ttl=None):
    client.set(key, _dump(client, value), ttl=ttl)


def _children(client, prefix):
    """
    Return ``{relative key: value}`` for the keys under ``prefix/``
    """
    ret = {}
    start = len(prefix) + 1
    for kv in client.read(prefix, recurse=True) or []:
        if len(kv.key) > start:
            ret[kv.key[start:]] = kv.value
    return ret


def _jids(client, path):
    """
    Return the job IDs that have anything stored under them
    """
    return sorted({key.split("/", 1)[0] for key in _children(client, f"{path}/jobs")})


def returner(ret):
    """
    Return data to an etcd server or cluster
    """
    if ret["jid"] == "req":
        ret["jid"] = prep_jid(nocache=ret.get("nocache", False))

    client, path, ttl = _write_conn()
    job = f"{path}/jobs/{ret['jid']}"
    if client.get(f"{job}/{_NOCACHE}") is not None:
        return

    # Make a note of this minion for the external job cache
    _set(client, f"{path}/minions/{ret['id']}", ret["jid"], ttl=ttl)
    record = {field: ret[field] for field in _RETURN_FIELDS if field in ret}
    _set(client, f"{job}/{ret['id']}", record, ttl=ttl)


def save_load(jid, load, minions=None):
    """
    Save the load to the specified jid
    """
    log.debug("etcd returner <save_load> called jid: %s", jid)
    client, path, ttl = _write_conn()
    _set(client, f"{path}/jobs/{jid}/{_LOAD}", load, ttl=ttl)
    if load.get("tgt"):
        if minions is None:
            ckminions = salt.utils.minions.CkMinions(__opts__)
            minions = ckminions.check_minions(
                load["tgt"], load.get("tgt_type", "glob")
            )["minions"]
        save_minions(jid, minions)


def save_minions(jid, minions, syndic_id=None):  # pylint: disable=unused-argument
    """
    Save the minions targeted by a job, merged with any already saved
    """
    client, path, ttl = _write_conn()
    key = f"{path}/jobs/{jid}/{_MINIONS}"
    existing = _get(client, key) or []
    _set(client, key, sorted(set(existing) | set(minions or [])), ttl=ttl)


def get_load(jid):
    """
    Return the load data that marks a specified jid, with the targeted
    minions under ``Minions``
    """
    log.debug("etcd returner <get_load> called jid: %s", jid)
    client, path = _read_conn()
    load = _get(client, f"{path}/jobs/{jid}/{_LOAD}")
    if not load:
        return {}
    minions = _get(client, f"{path}/jobs/{jid}/{_MINIONS}")
    if minions:
        load["Minions"] = minions
    return load


def get_jid(jid):
    """
    Return the information returned when the specified job id was executed
    """
    log.debug("etcd returner <get_jid> called jid: %s", jid)
    client, path = _read_conn()
    ret = {}
    for minion_id, value in _children(client, f"{path}/jobs/{jid}").items():
        if minion_id.startswith("."):
            continue
        ret[minion_id] = _load(client, value)
    return ret


def get_fun(fun):
    """
    Return a dict of the last function called for all minions
    """
    log.debug("etcd returner <get_fun> called fun: %s", fun)
    client, path = _read_conn()
    ret = {}
    for minion_id, jid in _children(client, f"{path}/minions").items():
        record = _get(client, f"{path}/jobs/{_load(client, jid)}/{minion_id}")
        if record and record.get("fun") == fun:
            ret[minion_id] = fun
    return ret


def get_jids():
    """
    Return a dict mapping all job ids to job information
    """
    log.debug("etcd returner <get_jids> called")
    client, path = _read_conn()
    ret = {}
    for jid in _jids(client, path):
        load = _get(client, f"{path}/jobs/{jid}/{_LOAD}")
        if load:
            ret[jid] = salt.utils.jid.format_jid_instance(jid, load)
    return ret


def get_jids_filter(count, filter_find_job=True):
    """
    Return the ``count`` most recent jobs, optionally without
    ``saltutil.find_job`` calls
    """
    client, path = _read_conn()
    ret = []
    for jid in reversed(_jids(client, path)):
        load = _get(client, f"{path}/jobs/{jid}/{_LOAD}")
        if not load:
            continue
        job = salt.utils.jid.format_jid_instance_ext(jid, load)
        if filter_find_job and job.get("Function") == "saltutil.find_job":
            continue
        ret.append(job)
        if len(ret) == count:
            break
    return list(reversed(ret))


def get_minions():
    """
    Return a list of minions
    """
    log.debug("etcd returner <get_minions> called")
    client, path = _read_conn()
    return sorted(_children(client, f"{path}/minions"))


def prep_jid(nocache=False, passed_jid=None):
    """
    Do any work necessary to prepare a JID, including sending a custom id
    """
    jid = passed_jid if passed_jid is not None else salt.utils.jid.gen_jid(__opts__)
    if nocache:
        client, path, ttl = _write_conn()
        _set(client, f"{path}/jobs/{jid}/{_NOCACHE}", True, ttl=ttl)
    return jid


def update_endtime(jid, time):
    """
    Save the end time of a job
    """
    client, path, ttl = _write_conn()
    _set(client, f"{path}/jobs/{jid}/{_ENDTIME}", time, ttl=ttl)


def get_endtime(jid):
    """
    Return the end time of a job, or ``False`` if it was not saved
    """
    client, path = _read_conn()
    return _get(client, f"{path}/jobs/{jid}/{_ENDTIME}") or False


def clean_old_jobs():
    """
    Remove jobs older than ``keep_jobs_seconds``
    """
    keep_jobs_seconds = salt.utils.job.get_keep_jobs_seconds(__opts__)
    if not keep_jobs_seconds:
        return
    cutoff = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(
        seconds=keep_jobs_seconds
    )
    client, path, _ = _write_conn()
    for jid in _jids(client, path):
        try:
            started = datetime.datetime.strptime(jid[:20], "%Y%m%d%H%M%S%f").replace(
                tzinfo=datetime.timezone.utc
            )
        except ValueError:
            log.debug("etcd returner: skipping %s, not a job ID", jid)
            continue
        if started < cutoff:
            client.delete(f"{path}/jobs/{jid}", recurse=True)
