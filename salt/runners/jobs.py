"""
A convenience system to manage jobs, both active and already run
"""

import fnmatch
import logging
import os

import salt.client
import salt.minion
import salt.payload
import salt.returners
import salt.utils.args
import salt.utils.files
import salt.utils.jid
import salt.utils.master
from salt.exceptions import SaltClientError

try:
    import dateutil.parser as dateutil_parser

    DATEUTIL_SUPPORT = True
except ImportError:
    DATEUTIL_SUPPORT = False

log = logging.getLogger(__name__)


def master():
    """
    Return the actively executing runners for the master

    CLI Example:

    .. code-block:: bash

        salt-run jobs.master
    """
    return salt.utils.master.get_running_jobs(__opts__)


def active(display_progress=False):
    """
    Return a report on all actively running jobs from a job id centric
    perspective

    CLI Example:

    .. code-block:: bash

        salt-run jobs.active
    """
    ret = {}
    with salt.client.get_local_client(__opts__["conf_file"]) as client:
        try:
            active_ = client.cmd("*", "saltutil.running", timeout=__opts__["timeout"])
        except SaltClientError as client_error:
            print(client_error)
            return ret

    if display_progress:
        __jid_event__.fire_event(
            {
                "message": "Attempting to contact minions: {}".format(
                    list(active_.keys())
                )
            },
            "progress",
        )
    for minion, data in active_.items():
        if display_progress:
            __jid_event__.fire_event(
                {"message": "Received reply from minion {}".format(minion)}, "progress"
            )
        if not isinstance(data, list):
            continue
        for job in data:
            if not job["jid"] in ret:
                ret[job["jid"]] = _format_jid_instance(job["jid"], job)
                ret[job["jid"]].update(
                    {"Running": [{minion: job.get("pid", None)}], "Returned": []}
                )
            else:
                ret[job["jid"]]["Running"].append({minion: job["pid"]})

    mminion = salt.minion.MasterMinion(__opts__)
    for jid in ret:
        returner = _get_returner(
            (__opts__["ext_job_cache"], __opts__["master_job_cache"])
        )
        data = mminion.returners["{}.get_jid".format(returner)](jid)
        if data:
            for minion in data:
                if minion not in ret[jid]["Returned"]:
                    ret[jid]["Returned"].append(minion)

    return ret


def lookup_jid(
    jid, ext_source=None, returned=True, missing=False, display_progress=False
):
    """
    Return the printout from a previously executed job

    jid
        The jid to look up.

    ext_source
        The external job cache to use. Default: `None`.

    returned : True
        If ``True``, include the minions that did return from the command.

        .. versionadded:: 2015.8.0

    missing : False
        If ``True``, include the minions that did *not* return from the
        command.

    display_progress : False
        If ``True``, fire progress events.

        .. versionadded:: 2015.5.0

    CLI Example:

    .. code-block:: bash

        salt-run jobs.lookup_jid 20130916125524463507
        salt-run jobs.lookup_jid 20130916125524463507 --out=highstate
    """
    ret = {}
    mminion = salt.minion.MasterMinion(__opts__)
    returner = _get_returner(
        (__opts__["ext_job_cache"], ext_source, __opts__["master_job_cache"])
    )

    try:
        data = list_job(jid, ext_source=ext_source, display_progress=display_progress)
    except TypeError:
        return "Requested returner could not be loaded. No JIDs could be retrieved."

    targeted_minions = data.get("Minions", [])
    returns = data.get("Result", {})

    if returns:
        for minion in returns:
            if display_progress:
                __jid_event__.fire_event({"message": minion}, "progress")
            if "return" in returns[minion]:
                if returned:
                    ret[minion] = returns[minion].get("return")
            else:
                if returned:
                    ret[minion] = returns[minion].get("return")
    if missing:
        for minion_id in (x for x in targeted_minions if x not in returns):
            ret[minion_id] = "Minion did not return"

    # We need to check to see if the 'out' key is present and use it to specify
    # the correct outputter, so we get highstate output for highstate runs.
    try:
        # Check if the return data has an 'out' key. We'll use that as the
        # outputter in the absence of one being passed on the CLI.
        outputter = returns[next(iter(returns))].get("out")
    except (StopIteration, AttributeError):
        outputter = None

    if outputter:
        return {"outputter": outputter, "data": ret}
    else:
        return ret


def list_job(jid, ext_source=None, display_progress=False):
    """
    List a specific job given by its jid

    ext_source
        If provided, specifies which external job cache to use.

    display_progress : False
        If ``True``, fire progress events.

        .. versionadded:: 2015.8.8

    CLI Example:

    .. code-block:: bash

        salt-run jobs.list_job 20130916125524463507
        salt-run jobs.list_job 20130916125524463507 --out=pprint
    """
    ret = {"jid": jid}
    mminion = salt.minion.MasterMinion(__opts__)
    returner = _get_returner(
        (__opts__["ext_job_cache"], ext_source, __opts__["master_job_cache"])
    )
    if display_progress:
        __jid_event__.fire_event(
            {"message": "Querying returner: {}".format(returner)}, "progress"
        )

    job = mminion.returners["{}.get_load".format(returner)](jid)
    ret.update(_format_jid_instance(jid, job))
    ret["Result"] = mminion.returners["{}.get_jid".format(returner)](jid)

    fstr = "{}.get_endtime".format(__opts__["master_job_cache"])
    if __opts__.get("job_cache_store_endtime") and fstr in mminion.returners:
        endtime = mminion.returners[fstr](jid)
        if endtime:
            ret["EndTime"] = endtime

    return ret


def list_jobs(
    ext_source=None,
    outputter=None,
    search_metadata=None,
    search_function=None,
    search_target=None,
    start_time=None,
    end_time=None,
    display_progress=False,
):
    """
    List all detectable jobs and associated functions

    ext_source
        If provided, specifies which external job cache to use.

    **FILTER OPTIONS**

    .. note::
        If more than one of the below options are used, only jobs which match
        *all* of the filters will be returned.

    search_metadata
        Specify a dictionary to match to the job's metadata. If any of the
        key-value pairs in this dictionary match, the job will be returned.
        Example:

        .. code-block:: bash

            salt-run jobs.list_jobs search_metadata='{"foo": "bar", "baz": "qux"}'

    search_function
        Can be passed as a string or a list. Returns jobs which match the
        specified function. Globbing is allowed. Example:

        .. code-block:: bash

            salt-run jobs.list_jobs search_function='test.*'
            salt-run jobs.list_jobs search_function='["test.*", "pkg.install"]'

        .. versionchanged:: 2015.8.8
            Multiple targets can now also be passed as a comma-separated list.
            For example:

            .. code-block:: bash

                salt-run jobs.list_jobs search_function='test.*,pkg.install'

    search_target
        Can be passed as a string or a list. Returns jobs which match the
        specified minion name. Globbing is allowed. Example:

        .. code-block:: bash

            salt-run jobs.list_jobs search_target='*.mydomain.tld'
            salt-run jobs.list_jobs search_target='["db*", "myminion"]'

        .. versionchanged:: 2015.8.8
            Multiple targets can now also be passed as a comma-separated list.
            For example:

            .. code-block:: bash

                salt-run jobs.list_jobs search_target='db*,myminion'

    start_time
        Accepts any timestamp supported by the dateutil_ Python module (if this
        module is not installed, this argument will be ignored). Returns jobs
        which started after this timestamp.

    end_time
        Accepts any timestamp supported by the dateutil_ Python module (if this
        module is not installed, this argument will be ignored). Returns jobs
        which started before this timestamp.

    .. _dateutil: https://pypi.python.org/pypi/python-dateutil

    CLI Example:

    .. code-block:: bash

        salt-run jobs.list_jobs
        salt-run jobs.list_jobs search_function='test.*' search_target='localhost' search_metadata='{"bar": "foo"}'
        salt-run jobs.list_jobs start_time='2015, Mar 16 19:00' end_time='2015, Mar 18 22:00'

    """
    returner = _get_returner(
        (__opts__["ext_job_cache"], ext_source, __opts__["master_job_cache"])
    )
    if display_progress:
        __jid_event__.fire_event(
            {"message": "Querying returner {} for jobs.".format(returner)}, "progress"
        )
    mminion = salt.minion.MasterMinion(__opts__)

    ret = mminion.returners["{}.get_jids".format(returner)]()

    mret = {}
    for item in ret:
        _match = True
        if search_metadata:
            _match = False
            if "Metadata" in ret[item]:
                if isinstance(search_metadata, dict):
                    for key in search_metadata:
                        if key in ret[item]["Metadata"]:
                            if ret[item]["Metadata"][key] == search_metadata[key]:
                                _match = True
                else:
                    log.info(
                        "The search_metadata parameter must be specified"
                        " as a dictionary.  Ignoring."
                    )
        if search_target and _match:
            _match = False
            if "Target" in ret[item]:
                targets = ret[item]["Target"]
                if isinstance(targets, str):
                    targets = [targets]
                for target in targets:
                    for key in salt.utils.args.split_input(search_target):
                        if fnmatch.fnmatch(target, key):
                            _match = True

        if search_function and _match:
            _match = False
            if "Function" in ret[item]:
                for key in salt.utils.args.split_input(search_function):
                    if fnmatch.fnmatch(ret[item]["Function"], key):
                        _match = True

        if start_time and _match:
            _match = False
            if DATEUTIL_SUPPORT:
                parsed_start_time = dateutil_parser.parse(start_time)
                _start_time = dateutil_parser.parse(ret[item]["StartTime"])
                if _start_time >= parsed_start_time:
                    _match = True
            else:
                log.error(
                    "'dateutil' library not available, skipping start_time comparison."
                )

        if end_time and _match:
            _match = False
            if DATEUTIL_SUPPORT:
                parsed_end_time = dateutil_parser.parse(end_time)
                _start_time = dateutil_parser.parse(ret[item]["StartTime"])
                if _start_time <= parsed_end_time:
                    _match = True
            else:
                log.error(
                    "'dateutil' library not available, skipping end_time comparison."
                )

        if _match:
            mret[item] = ret[item]

    if outputter:
        return {"outputter": outputter, "data": mret}
    else:
        return mret


def list_jobs_filter(
    count, filter_find_job=True, ext_source=None, outputter=None, display_progress=False
):
    """
    List all detectable jobs and associated functions

    ext_source
        The external job cache to use. Default: `None`.

    CLI Example:

    .. code-block:: bash

        salt-run jobs.list_jobs_filter 50
        salt-run jobs.list_jobs_filter 100 filter_find_job=False

    """
    returner = _get_returner(
        (__opts__["ext_job_cache"], ext_source, __opts__["master_job_cache"])
    )
    if display_progress:
        __jid_event__.fire_event(
            {"message": "Querying returner {} for jobs.".format(returner)}, "progress"
        )
    mminion = salt.minion.MasterMinion(__opts__)

    fun = "{}.get_jids_filter".format(returner)
    if fun not in mminion.returners:
        raise NotImplementedError(
            "'{}' returner function not implemented yet.".format(fun)
        )
    ret = mminion.returners[fun](count, filter_find_job)

    if outputter:
        return {"outputter": outputter, "data": ret}
    else:
        return ret


def print_job(jid, ext_source=None):
    """
    Print a specific job's detail given by its jid, including the return data.

    CLI Example:

    .. code-block:: bash

        salt-run jobs.print_job 20130916125524463507
    """
    ret = {}

    returner = _get_returner(
        (__opts__["ext_job_cache"], ext_source, __opts__["master_job_cache"])
    )
    mminion = salt.minion.MasterMinion(__opts__)

    try:
        job = mminion.returners["{}.get_load".format(returner)](jid)
        ret[jid] = _format_jid_instance(jid, job)
    except TypeError:
        ret[jid]["Result"] = (
            "Requested returner {} is not available. Jobs cannot be "
            "retrieved. Check master log for details.".format(returner)
        )
        return ret
    ret[jid]["Result"] = mminion.returners["{}.get_jid".format(returner)](jid)

    fstr = "{}.get_endtime".format(__opts__["master_job_cache"])
    if __opts__.get("job_cache_store_endtime") and fstr in mminion.returners:
        endtime = mminion.returners[fstr](jid)
        if endtime:
            ret[jid]["EndTime"] = endtime

    return ret


def exit_success(jid, ext_source=None):
    """
    Check if a job has been executed and exit successfully

    jid
        The jid to look up.
    ext_source
        The external job cache to use. Default: `None`.

    CLI Example:

    .. code-block:: bash

        salt-run jobs.exit_success 20160520145827701627
    """
    ret = dict()

    data = list_job(jid, ext_source=ext_source)

    minions = data.get("Minions", [])
    result = data.get("Result", {})

    for minion in minions:
        if minion in result and "return" in result[minion]:
            ret[minion] = True if result[minion]["return"] else False
        else:
            ret[minion] = False

    for minion in result:
        if "return" in result[minion] and result[minion]["return"]:
            ret[minion] = True
    return ret


def last_run(
    ext_source=None,
    outputter=None,
    metadata=None,
    function=None,
    target=None,
    display_progress=False,
):
    """
    .. versionadded:: 2015.8.0

    List all detectable jobs and associated functions

    CLI Example:

    .. code-block:: bash

        salt-run jobs.last_run
        salt-run jobs.last_run target=nodename
        salt-run jobs.last_run function='cmd.run'
        salt-run jobs.last_run metadata="{'foo': 'bar'}"
    """

    if metadata:
        if not isinstance(metadata, dict):
            log.info("The metadata parameter must be specified as a dictionary")
            return False

    _all_jobs = list_jobs(
        ext_source=ext_source,
        outputter=outputter,
        search_metadata=metadata,
        search_function=function,
        search_target=target,
        display_progress=display_progress,
    )
    if _all_jobs:
        last_job = sorted(_all_jobs)[-1]
        return print_job(last_job, ext_source)
    else:
        return False


def _get_returner(returner_types):
    """
    Helper to iterate over returner_types and pick the first one
    """
    for returner in returner_types:
        if returner and returner is not None:
            return returner


def _format_job_instance(job):
    """
    Helper to format a job instance
    """
    if not job:
        ret = {"Error": "Cannot contact returner or no job with this jid"}
        return ret

    ret = {
        "Function": job.get("fun", "unknown-function"),
        "Arguments": list(job.get("arg", [])),
        # unlikely but safeguard from invalid returns
        "Target": job.get("tgt", "unknown-target"),
        "Target-type": job.get("tgt_type", "list"),
        "User": job.get("user", "root"),
    }

    if "metadata" in job:
        ret["Metadata"] = job.get("metadata", {})
    else:
        if "kwargs" in job:
            if "metadata" in job["kwargs"]:
                ret["Metadata"] = job["kwargs"].get("metadata", {})

    if "Minions" in job:
        ret["Minions"] = job["Minions"]
    return ret


def _format_jid_instance(jid, job):
    """
    Helper to format jid instance
    """
    ret = _format_job_instance(job)
    ret.update({"StartTime": salt.utils.jid.jid_to_time(jid)})
    return ret


def _walk_through(job_dir, display_progress=False):
    """
    Walk through the job dir and return jobs
    """
    for top in os.listdir(job_dir):
        t_path = os.path.join(job_dir, top)

        for final in os.listdir(t_path):
            load_path = os.path.join(t_path, final, ".load.p")
            with salt.utils.files.fopen(load_path, "rb") as rfh:
                job = salt.payload.load(rfh)

            if not os.path.isfile(load_path):
                continue

            with salt.utils.files.fopen(load_path, "rb") as rfh:
                job = salt.payload.load(rfh)
            jid = job["jid"]
            if display_progress:
                __jid_event__.fire_event(
                    {"message": "Found JID {}".format(jid)}, "progress"
                )
            yield jid, job, t_path, final
