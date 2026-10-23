"""
Read/Write multiple returners

"""

import logging
from typing import TYPE_CHECKING, Any

import salt.minion

log = logging.getLogger(__name__)

CONFIG_KEY = "multi_returner"

# cache of the master mininon for this returner
MMINION = None

# ``__opts__`` is injected into this module's namespace by the salt loader at
# load time. The guarded declaration below only serves static analysis (the
# ``TYPE_CHECKING`` branch never runs, so no runtime binding is created); the
# ``= {}`` placeholder makes it count as a definition for ruff as well.
if TYPE_CHECKING:
    __opts__: dict[str, Any] = {}


def _mminion():
    """
    Create a single mminion for this module to use, instead of reloading all the time
    """
    global MMINION  # pylint: disable=global-statement

    if MMINION is None:
        MMINION = salt.minion.MasterMinion(__opts__)

    return MMINION


def prep_jid(nocache=False, passed_jid=None):
    """
    Call both with prep_jid on all returners in multi_returner

    TODO: finish this, what do do when you get different jids from 2 returners...
    since our jids are time based, this make this problem hard, because they
    aren't unique, meaning that we have to make sure that no one else got the jid
    and if they did we spin to get a new one, which means "locking" the jid in 2
    returners is non-trivial
    """

    jid = passed_jid
    for returner_ in __opts__[CONFIG_KEY]:
        if jid is None:
            jid = _mminion().returners[f"{returner_}.prep_jid"](nocache=nocache)
        else:
            r_jid = _mminion().returners[f"{returner_}.prep_jid"](nocache=nocache)
            if r_jid != jid:
                log.debug("Uhh.... crud the jids do not match")
    return jid


def returner(load):
    """
    Write return to all returners in multi_returner
    """
    for returner_ in __opts__[CONFIG_KEY]:
        _mminion().returners[f"{returner_}.returner"](load)


def save_load(jid, clear_load, minions=None):
    """
    Write load to all returners in multi_returner

    Loads whose ``cmd`` is ``_return`` are skipped for ``local_cache`` only,
    so a minion return does not overwrite the master's dispatch-time load;
    every other returner receives all loads.
    """
    for returner_ in __opts__[CONFIG_KEY]:
        if returner_ == "local_cache":
            cmd = clear_load.get("cmd")
            if cmd == "_return":
                continue
        _mminion().returners[f"{returner_}.save_load"](jid, clear_load, minions)


def save_minions(jid, minions, syndic_id=None):
    """
    Write the minion list to all returners in multi_returner that support it
    """
    for returner_ in __opts__[CONFIG_KEY]:
        fstr = f"{returner_}.save_minions"
        if fstr in _mminion().returners:
            _mminion().returners[fstr](jid, minions, syndic_id)


def get_load(jid):
    """
    Merge the load data from all returners
    """
    ret = {}
    for returner_ in __opts__[CONFIG_KEY]:
        ret.update(_mminion().returners[f"{returner_}.get_load"](jid))

    return ret


def get_jid(jid):
    """
    Merge the return data from all returners
    """
    ret = {}
    for returner_ in __opts__[CONFIG_KEY]:
        ret.update(_mminion().returners[f"{returner_}.get_jid"](jid))

    return ret


def get_jids():
    """
    Return all job data from all returners
    """
    ret = {}
    for returner_ in __opts__[CONFIG_KEY]:
        ret.update(_mminion().returners[f"{returner_}.get_jids"]())

    return ret


def get_jids_filter(count, filter_find_job=True):
    """
    Return a list of the most recent jobs from all returners in
    multi_returner, deduplicated by jid and capped at ``count``.

    :param int count: show not more than the count of most recent jobs
    :param bool filter_find_job: filter out 'saltutil.find_job' jobs
    """
    merged = {}
    for returner_ in __opts__[CONFIG_KEY]:
        fstr = f"{returner_}.get_jids_filter"
        if fstr in _mminion().returners:
            for job in _mminion().returners[fstr](count, filter_find_job):
                merged[job["JID"]] = job

    if count <= 0:
        return []
    return [merged[jid] for jid in sorted(merged)[-count:]]


def clean_old_jobs():
    """
    Clean out the old jobs from all returners (if you have it)
    """
    for returner_ in __opts__[CONFIG_KEY]:
        fstr = f"{returner_}.clean_old_jobs"
        if fstr in _mminion().returners:
            _mminion().returners[fstr]()


def update_endtime(jid, time):
    """
    Update (or store) the end time for a given job

    Endtime is stored as a plain text string
    """
    for returner_ in __opts__[CONFIG_KEY]:
        fstr = f"{returner_}.update_endtime"
        if fstr in _mminion().returners:
            _mminion().returners[fstr](jid, time)


def get_endtime(jid):
    """
    Return the end time for a given job

    Returns the first end time found in the configured returners (in
    configuration order), or False when no returner has one
    """
    for returner_ in __opts__[CONFIG_KEY]:
        fstr = f"{returner_}.get_endtime"
        if fstr in _mminion().returners:
            endtime = _mminion().returners[fstr](jid)
            if endtime:
                return endtime
    return False


def save_reg(data):
    """
    Save the register to msgpack files

    Writes to every configured returner that implements ``save_reg`` so the
    multi_returner write-to-all contract is preserved.
    """
    for returner_ in __opts__[CONFIG_KEY]:
        fstr = f"{returner_}.save_reg"
        if fstr in _mminion().returners:
            _mminion().returners[fstr](data)


def load_reg():
    """
    Load the register from msgpack files
    """
    for returner_ in __opts__[CONFIG_KEY]:
        fstr = f"{returner_}.load_reg"
        if fstr in _mminion().returners:
            return _mminion().returners[fstr]()
