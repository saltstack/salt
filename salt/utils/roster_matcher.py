"""
Roster matching by various criteria (glob, pcre, etc)
"""

import copy
import fnmatch
import functools
import logging
import re

from salt.utils.decorators.dunder_utils import deprecated

# Try to import range from https://github.com/ytoolshed/range
HAS_RANGE = False
try:
    import seco.range

    HAS_RANGE = True
except ImportError:
    pass
# pylint: enable=import-error


log = logging.getLogger(__name__)


def targets(
    conditioned_raw,
    tgt,
    tgt_type,
    ipv="ipv4",
    ssh_list_nodegroups=None,
    range_server=None,
    roster_defaults=None,
):
    """
    Execute the correct tgt_type match routine and return the found targets
    """
    rmatcher = RosterMatcher(
        conditioned_raw,
        tgt,
        tgt_type,
        ipv=ipv,
        ssh_list_nodegroups=ssh_list_nodegroups,
        range_server=range_server,
        roster_defaults=roster_defaults,
    )
    return rmatcher.targets()


@deprecated(by=targets)
def old_targets(conditioned_raw, tgt, tgt_type, ipv="ipv4"):
    """
    This docstring will be repalced but the docstring of function passed in
    ``by`` on the ``deprecated`` decorator.
    """
    return targets(
        conditioned_raw,
        tgt,
        tgt_type,
        ipv=ipv,
        ssh_list_nodegroups=__opts__.get("ssh_list_nodegroups"),
        range_server=__opts__.get("range_server"),
        roster_defaults=__opts__.get("roster_defaults"),
    )


def _tgt_set(tgt):
    """
    Return the tgt as a set of literal names
    """
    try:
        # A comma-delimited string
        return set(tgt.split(","))
    except AttributeError:
        # Assume tgt is already a non-string iterable.
        return set(tgt)


class RosterMatcher:
    """
    Matcher for the roster data structure
    """

    def __init__(
        self,
        raw,
        tgt,
        tgt_type,
        ipv="ipv4",
        ssh_list_nodegroups=None,
        range_server=None,
        roster_defaults=None,
    ):
        self.tgt = tgt
        self.tgt_type = tgt_type
        self.raw = raw
        self.ipv = ipv
        self.ssh_list_nodegroups = ssh_list_nodegroups
        self.range_server = range_server
        if roster_defaults is None:
            roster_defaults = {}
        self.roster_defaults = roster_defaults

    def targets(self):
        """
        Execute the correct tgt_type routine and return
        """
        try:
            tgt_type_func = getattr(self, "ret_{}_minions".format(self.tgt_type))
        except AttributeError:
            return {}
        else:
            return tgt_type_func()

    def _ret_minions(self, filter_):
        """
        Filter minions by a generic filter.
        """
        minions = {}
        for minion in filter_(self.raw):
            data = self.get_data(minion)
            if data:
                minions[minion] = data.copy()
        return minions

    def ret_glob_minions(self):
        """
        Return minions that match via glob
        """
        fnfilter = functools.partial(fnmatch.filter, pat=self.tgt)
        return self._ret_minions(fnfilter)

    def ret_pcre_minions(self):
        """
        Return minions that match via pcre
        """
        tgt = re.compile(self.tgt)
        refilter = functools.partial(filter, tgt.match)
        return self._ret_minions(refilter)

    def ret_list_minions(self):
        """
        Return minions that match via list
        """
        tgt = _tgt_set(self.tgt)
        return self._ret_minions(tgt.intersection)

    def ret_nodegroup_minions(self):
        """
        Return minions which match the special list-only groups defined by
        ssh_list_nodegroups
        """
        if self.ssh_list_nodegroups:
            nodegroup = self.ssh_list_nodegroups.get(self.tgt, [])
        else:
            nodegroup = []
        nodegroup = _tgt_set(nodegroup)
        return self._ret_minions(nodegroup.intersection)

    def ret_range_minions(self):
        """
        Return minions that are returned by a range query
        """
        if HAS_RANGE is False:
            raise RuntimeError("Python lib 'seco.range' is not available")

        range_hosts = _convert_range_to_list(self.tgt, self.range_server)
        return self._ret_minions(range_hosts.__contains__)

    def get_data(self, minion, roster_defaults=None):
        """
        Return the configured ip
        """
        if roster_defaults is None:
            roster_defaults = {}
        ret = copy.deepcopy(roster_defaults)
        if isinstance(self.raw[minion], str):
            ret.update({"host": self.raw[minion]})
            return ret
        elif isinstance(self.raw[minion], dict):
            ret.update(self.raw[minion])
            return ret
        return False


def _convert_range_to_list(tgt, range_server):
    """
    convert a seco.range range into a list target
    """
    r = seco.range.Range(range_server)
    try:
        return r.expand(tgt)
    except seco.range.RangeException as err:
        log.error("Range server exception: %s", err)
        return []
