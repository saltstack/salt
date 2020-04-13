# -*- coding: utf-8 -*-
"""
This module contains routines used to verify the matcher against the minions
expected to return
"""

# Import python libs
from __future__ import absolute_import, unicode_literals

import fnmatch
import logging
import os
import re

import salt.auth.ldap
import salt.cache

# Import salt libs
import salt.payload
import salt.roster
import salt.utils.data
import salt.utils.files
import salt.utils.network
import salt.utils.stringutils
import salt.utils.versions

# Import 3rd-party libs
from salt._compat import ipaddress
from salt.defaults import DEFAULT_TARGET_DELIM
from salt.exceptions import CommandExecutionError, SaltCacheError
from salt.ext import six

HAS_RANGE = False
try:
    import seco.range  # pylint: disable=import-error

    HAS_RANGE = True
except ImportError:
    pass

log = logging.getLogger(__name__)

TARGET_REX = re.compile(
    r"""(?x)
        (
            (?P<engine>G|P|I|J|L|N|S|E|R)  # Possible target engines
            (?P<delimiter>(?<=G|P|I|J).)?  # Optional delimiter for specific engines
        @)?                                # Engine+delimiter are separated by a '@'
                                           # character and are optional for the target
        (?P<pattern>.+)$"""  # The pattern passed to the target engine
)


def _nodegroup_regex(nodegroup, words, opers):
    opers_set = set(opers)
    ret = words
    if (set(ret) - opers_set) == set(ret):
        # No compound operators found in nodegroup definition. Check for
        # group type specifiers
        group_type_re = re.compile("^[A-Z]@")
        regex_chars = ["(", "[", "{", "\\", "?", "}", "]", ")"]
        if not [x for x in ret if "*" in x or group_type_re.match(x)]:
            # No group type specifiers and no wildcards.
            # Treat this as an expression.
            if [x for x in ret if x in [x for y in regex_chars if y in x]]:
                joined = "E@" + ",".join(ret)
                log.debug(
                    "Nodegroup '%s' (%s) detected as an expression. "
                    "Assuming compound matching syntax of '%s'",
                    nodegroup,
                    ret,
                    joined,
                )
            else:
                # Treat this as a list of nodenames.
                joined = "L@" + ",".join(ret)
                log.debug(
                    "Nodegroup '%s' (%s) detected as list of nodenames. "
                    "Assuming compound matching syntax of '%s'",
                    nodegroup,
                    ret,
                    joined,
                )
            # Return data must be a list of compound matching components
            # to be fed into compound matcher. Enclose return data in list.
            return [joined]


def parse_target(target_expression):
    """Parse `target_expressing` splitting it into `engine`, `delimiter`,
     `pattern` - returns a dict"""

    match = TARGET_REX.match(target_expression)
    if not match:
        log.warning('Unable to parse target "%s"', target_expression)
        ret = {
            "engine": None,
            "delimiter": None,
            "pattern": target_expression,
        }
    else:
        ret = match.groupdict()
    return ret


def get_minion_data(minion, opts):
    """
    Get the grains/pillar for a specific minion.  If minion is None, it
    will return the grains/pillar for the first minion it finds.

    Return value is a tuple of the minion ID, grains, and pillar
    """
    grains = None
    pillar = None
    if opts.get("minion_data_cache", False):
        cache = salt.cache.factory(opts)
        if minion is None:
            for id_ in cache.list("minions"):
                data = cache.fetch("minions/{0}".format(id_), "data")
                if data is None:
                    continue
        else:
            data = cache.fetch("minions/{0}".format(minion), "data")
        if data is not None:
            grains = data.get("grains", None)
            pillar = data.get("pillar", None)
    return minion if minion else None, grains, pillar


def nodegroup_comp(nodegroup, nodegroups, skip=None, first_call=True):
    """
    Recursively expand ``nodegroup`` from ``nodegroups``; ignore nodegroups in ``skip``

    If a top-level (non-recursive) call finds no nodegroups, return the original
    nodegroup definition (for backwards compatibility). Keep track of recursive
    calls via `first_call` argument
    """
    expanded_nodegroup = False
    if skip is None:
        skip = set()
    elif nodegroup in skip:
        log.error(
            'Failed nodegroup expansion: illegal nested nodegroup "%s"', nodegroup
        )
        return ""

    if nodegroup not in nodegroups:
        log.error('Failed nodegroup expansion: unknown nodegroup "%s"', nodegroup)
        return ""

    nglookup = nodegroups[nodegroup]
    if isinstance(nglookup, six.string_types):
        words = nglookup.split()
    elif isinstance(nglookup, (list, tuple)):
        words = nglookup
    else:
        log.error(
            "Nodegroup '%s' (%s) is neither a string, list nor tuple",
            nodegroup,
            nglookup,
        )
        return ""

    skip.add(nodegroup)
    ret = []
    opers = ["and", "or", "not", "(", ")"]
    for word in words:
        if not isinstance(word, six.string_types):
            word = six.text_type(word)
        if word in opers:
            ret.append(word)
        elif len(word) >= 3 and word.startswith("N@"):
            expanded_nodegroup = True
            ret.extend(
                nodegroup_comp(word[2:], nodegroups, skip=skip, first_call=False)
            )
        else:
            ret.append(word)

    if ret:
        ret.insert(0, "(")
        ret.append(")")

    skip.remove(nodegroup)

    log.debug("nodegroup_comp(%s) => %s", nodegroup, ret)
    # Only return list form if a nodegroup was expanded. Otherwise return
    # the original string to conserve backwards compat
    if expanded_nodegroup or not first_call:
        if not first_call:
            joined = _nodegroup_regex(nodegroup, words, opers)
            if joined:
                return joined
        return ret
    else:
        ret = words
        joined = _nodegroup_regex(nodegroup, ret, opers)
        if joined:
            return joined

        log.debug(
            "No nested nodegroups detected. Using original nodegroup " "definition: %s",
            nodegroups[nodegroup],
        )
        return ret


class CkMinions(object):
    """
    Used to check what minions should respond from a target

    Note: This is a best-effort set of the minions that would match a target.
    Depending on master configuration (grains caching, etc.) and topology (syndics)
    the list may be a subset-- but we err on the side of too-many minions in this
    class.
    """

    def __init__(self, opts):
        self.opts = opts
        self.serial = salt.payload.Serial(opts)
        self.cache = salt.cache.factory(opts)
        # TODO: this is actually an *auth* check
        if self.opts.get("transport", "zeromq") in ("zeromq", "tcp"):
            self.acc = "minions"
        else:
            self.acc = "accepted"

    def _check_nodegroup_minions(self, expr, greedy):  # pylint: disable=unused-argument
        """
        Return minions found by looking at nodegroups
        """
        return self._check_compound_minions(
            nodegroup_comp(expr, self.opts["nodegroups"]), DEFAULT_TARGET_DELIM, greedy
        )

    def _check_glob_minions(self, expr, greedy):  # pylint: disable=unused-argument
        """
        Return the minions found by looking via globs
        """
        return {"minions": fnmatch.filter(self._pki_minions(), expr), "missing": []}

    def _check_list_minions(
        self, expr, greedy, ignore_missing=False
    ):  # pylint: disable=unused-argument
        """
        Return the minions found by looking via a list
        """
        if isinstance(expr, six.string_types):
            expr = [m for m in expr.split(",") if m]
        minions = self._pki_minions()
        return {
            "minions": [x for x in expr if x in minions],
            "missing": [] if ignore_missing else [x for x in expr if x not in minions],
        }

    def _check_pcre_minions(self, expr, greedy):  # pylint: disable=unused-argument
        """
        Return the minions found by looking via regular expressions
        """
        reg = re.compile(expr)
        return {
            "minions": [m for m in self._pki_minions() if reg.match(m)],
            "missing": [],
        }

    def _pki_minions(self):
        """
        Retreive complete minion list from PKI dir.
        Respects cache if configured
        """
        minions = []
        pki_cache_fn = os.path.join(self.opts["pki_dir"], self.acc, ".key_cache")
        try:
            os.makedirs(os.path.dirname(pki_cache_fn))
        except OSError:
            pass
        try:
            if self.opts["key_cache"] and os.path.exists(pki_cache_fn):
                log.debug("Returning cached minion list")
                if six.PY2:
                    with salt.utils.files.fopen(pki_cache_fn) as fn_:
                        return self.serial.load(fn_)
                else:
                    with salt.utils.files.fopen(pki_cache_fn, mode="rb") as fn_:
                        return self.serial.load(fn_)
            else:
                for fn_ in salt.utils.data.sorted_ignorecase(
                    os.listdir(os.path.join(self.opts["pki_dir"], self.acc))
                ):
                    if not fn_.startswith(".") and os.path.isfile(
                        os.path.join(self.opts["pki_dir"], self.acc, fn_)
                    ):
                        minions.append(fn_)
            return minions
        except OSError as exc:
            log.error(
                "Encountered OSError while evaluating minions in PKI dir: %s", exc
            )
            return minions

    def _check_cache_minions(
        self, expr, delimiter, greedy, search_type, regex_match=False, exact_match=False
    ):
        """
        Helper function to search for minions in master caches If 'greedy',
        then return accepted minions matched by the condition or those absent
        from the cache.  If not 'greedy' return the only minions have cache
        data and matched by the condition.
        """
        cache_enabled = self.opts.get("minion_data_cache", False)

        def list_cached_minions():
            return self.cache.list("minions")

        if greedy:
            minions = []
            for fn_ in salt.utils.data.sorted_ignorecase(
                os.listdir(os.path.join(self.opts["pki_dir"], self.acc))
            ):
                if not fn_.startswith(".") and os.path.isfile(
                    os.path.join(self.opts["pki_dir"], self.acc, fn_)
                ):
                    minions.append(fn_)
        elif cache_enabled:
            minions = list_cached_minions()
        else:
            return {"minions": [], "missing": []}

        if cache_enabled:
            if greedy:
                cminions = list_cached_minions()
            else:
                cminions = minions
            if not cminions:
                return {"minions": minions, "missing": []}
            minions = set(minions)
            for id_ in cminions:
                if greedy and id_ not in minions:
                    continue
                mdata = self.cache.fetch("minions/{0}".format(id_), "data")
                if mdata is None:
                    if not greedy:
                        minions.remove(id_)
                    continue
                search_results = mdata.get(search_type)
                if not salt.utils.data.subdict_match(
                    search_results,
                    expr,
                    delimiter=delimiter,
                    regex_match=regex_match,
                    exact_match=exact_match,
                ):
                    minions.remove(id_)
            minions = list(minions)
        return {"minions": minions, "missing": []}

    def _check_grain_minions(self, expr, delimiter, greedy):
        """
        Return the minions found by looking via grains
        """
        return self._check_cache_minions(expr, delimiter, greedy, "grains")

    def _check_grain_pcre_minions(self, expr, delimiter, greedy):
        """
        Return the minions found by looking via grains with PCRE
        """
        return self._check_cache_minions(
            expr, delimiter, greedy, "grains", regex_match=True
        )

    def _check_pillar_minions(self, expr, delimiter, greedy):
        """
        Return the minions found by looking via pillar
        """
        return self._check_cache_minions(expr, delimiter, greedy, "pillar")

    def _check_pillar_pcre_minions(self, expr, delimiter, greedy):
        """
        Return the minions found by looking via pillar with PCRE
        """
        return self._check_cache_minions(
            expr, delimiter, greedy, "pillar", regex_match=True
        )

    def _check_pillar_exact_minions(self, expr, delimiter, greedy):
        """
        Return the minions found by looking via pillar
        """
        return self._check_cache_minions(
            expr, delimiter, greedy, "pillar", exact_match=True
        )

    def _check_ipcidr_minions(self, expr, greedy):
        """
        Return the minions found by looking via ipcidr
        """
        cache_enabled = self.opts.get("minion_data_cache", False)

        if greedy:
            minions = self._pki_minions()
        elif cache_enabled:
            minions = self.cache.list("minions")
        else:
            return {"minions": [], "missing": []}

        if cache_enabled:
            if greedy:
                cminions = self.cache.list("minions")
            else:
                cminions = minions
            if cminions is None:
                return {"minions": minions, "missing": []}

            tgt = expr
            try:
                # Target is an address?
                tgt = ipaddress.ip_address(tgt)
            except Exception:  # pylint: disable=broad-except
                try:
                    # Target is a network?
                    tgt = ipaddress.ip_network(tgt)
                except Exception:  # pylint: disable=broad-except
                    log.error("Invalid IP/CIDR target: %s", tgt)
                    return {"minions": [], "missing": []}
            proto = "ipv{0}".format(tgt.version)

            minions = set(minions)
            for id_ in cminions:
                mdata = self.cache.fetch("minions/{0}".format(id_), "data")
                if mdata is None:
                    if not greedy:
                        minions.remove(id_)
                    continue
                grains = mdata.get("grains")
                if grains is None or proto not in grains:
                    match = False
                elif isinstance(tgt, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
                    match = six.text_type(tgt) in grains[proto]
                else:
                    match = salt.utils.network.in_subnet(tgt, grains[proto])

                if not match and id_ in minions:
                    minions.remove(id_)

        return {"minions": list(minions), "missing": []}

    def _check_range_minions(self, expr, greedy):
        """
        Return the minions found by looking via range expression
        """
        if not HAS_RANGE:
            raise CommandExecutionError(
                "Range matcher unavailable (unable to import seco.range, "
                "module most likely not installed)"
            )
        if not hasattr(self, "_range"):
            self._range = seco.range.Range(self.opts["range_server"])
        try:
            return self._range.expand(expr)
        except seco.range.RangeException as exc:
            log.error("Range exception in compound match: %s", exc)
            cache_enabled = self.opts.get("minion_data_cache", False)
            if greedy:
                mlist = []
                for fn_ in salt.utils.data.sorted_ignorecase(
                    os.listdir(os.path.join(self.opts["pki_dir"], self.acc))
                ):
                    if not fn_.startswith(".") and os.path.isfile(
                        os.path.join(self.opts["pki_dir"], self.acc, fn_)
                    ):
                        mlist.append(fn_)
                return {"minions": mlist, "missing": []}
            elif cache_enabled:
                return {"minions": self.cache.list("minions"), "missing": []}
            else:
                return {"minions": [], "missing": []}

    def _check_compound_pillar_exact_minions(self, expr, delimiter, greedy):
        """
        Return the minions found by looking via compound matcher

        Disable pillar glob matching
        """
        return self._check_compound_minions(expr, delimiter, greedy, pillar_exact=True)

    def _check_compound_minions(
        self, expr, delimiter, greedy, pillar_exact=False
    ):  # pylint: disable=unused-argument
        """
        Return the minions found by looking via compound matcher
        """
        if not isinstance(expr, six.string_types) and not isinstance(
            expr, (list, tuple)
        ):
            log.error("Compound target that is neither string, list nor tuple")
            return {"minions": [], "missing": []}
        minions = set(self._pki_minions())
        log.debug("minions: %s", minions)

        nodegroups = self.opts.get("nodegroups", {})

        if self.opts.get("minion_data_cache", False):
            ref = {
                "G": self._check_grain_minions,
                "P": self._check_grain_pcre_minions,
                "I": self._check_pillar_minions,
                "J": self._check_pillar_pcre_minions,
                "L": self._check_list_minions,
                "N": None,  # nodegroups should already be expanded
                "S": self._check_ipcidr_minions,
                "E": self._check_pcre_minions,
                "R": self._all_minions,
            }
            if pillar_exact:
                ref["I"] = self._check_pillar_exact_minions
                ref["J"] = self._check_pillar_exact_minions

            results = []
            unmatched = []
            opers = ["and", "or", "not", "(", ")"]
            missing = []

            if isinstance(expr, six.string_types):
                words = expr.split()
            else:
                # we make a shallow copy in order to not affect the passed in arg
                words = expr[:]

            while words:
                word = words.pop(0)
                target_info = parse_target(word)

                # Easy check first
                if word in opers:
                    if results:
                        if results[-1] == "(" and word in ("and", "or"):
                            log.error('Invalid beginning operator after "(": %s', word)
                            return {"minions": [], "missing": []}
                        if word == "not":
                            if not results[-1] in ("&", "|", "("):
                                results.append("&")
                            results.append("(")
                            results.append(six.text_type(set(minions)))
                            results.append("-")
                            unmatched.append("-")
                        elif word == "and":
                            results.append("&")
                        elif word == "or":
                            results.append("|")
                        elif word == "(":
                            results.append(word)
                            unmatched.append(word)
                        elif word == ")":
                            if not unmatched or unmatched[-1] != "(":
                                log.error(
                                    "Invalid compound expr (unexpected "
                                    "right parenthesis): %s",
                                    expr,
                                )
                                return {"minions": [], "missing": []}
                            results.append(word)
                            unmatched.pop()
                            if unmatched and unmatched[-1] == "-":
                                results.append(")")
                                unmatched.pop()
                        else:  # Won't get here, unless oper is added
                            log.error("Unhandled oper in compound expr: %s", expr)
                            return {"minions": [], "missing": []}
                    else:
                        # seq start with oper, fail
                        if word == "not":
                            results.append("(")
                            results.append(six.text_type(set(minions)))
                            results.append("-")
                            unmatched.append("-")
                        elif word == "(":
                            results.append(word)
                            unmatched.append(word)
                        else:
                            log.error(
                                "Expression may begin with" " binary operator: %s", word
                            )
                            return {"minions": [], "missing": []}

                elif target_info and target_info["engine"]:
                    if "N" == target_info["engine"]:
                        # if we encounter a node group, just evaluate it in-place
                        decomposed = nodegroup_comp(target_info["pattern"], nodegroups)
                        if decomposed:
                            words = decomposed + words
                        continue

                    engine = ref.get(target_info["engine"])
                    if not engine:
                        # If an unknown engine is called at any time, fail out
                        log.error(
                            'Unrecognized target engine "%s" for'
                            ' target expression "%s"',
                            target_info["engine"],
                            word,
                        )
                        return {"minions": [], "missing": []}

                    engine_args = [target_info["pattern"]]
                    if target_info["engine"] in ("G", "P", "I", "J"):
                        engine_args.append(target_info["delimiter"] or ":")
                    engine_args.append(greedy)

                    # ignore missing minions for lists if we exclude them with
                    # a 'not'
                    if "L" == target_info["engine"]:
                        engine_args.append(results and results[-1] == "-")
                    _results = engine(*engine_args)
                    results.append(six.text_type(set(_results["minions"])))
                    missing.extend(_results["missing"])
                    if unmatched and unmatched[-1] == "-":
                        results.append(")")
                        unmatched.pop()

                else:
                    # The match is not explicitly defined, evaluate as a glob
                    _results = self._check_glob_minions(word, True)
                    results.append(six.text_type(set(_results["minions"])))
                    if unmatched and unmatched[-1] == "-":
                        results.append(")")
                        unmatched.pop()

            # Add a closing ')' for each item left in unmatched
            results.extend([")" for item in unmatched])

            results = " ".join(results)
            log.debug("Evaluating final compound matching expr: %s", results)
            try:
                minions = list(eval(results))  # pylint: disable=W0123
                return {"minions": minions, "missing": missing}
            except Exception:  # pylint: disable=broad-except
                log.error("Invalid compound target: %s", expr)
                return {"minions": [], "missing": []}

        return {"minions": list(minions), "missing": []}

    def connected_ids(
        self, subset=None, show_ip=False, show_ipv4=None, include_localhost=None
    ):
        """
        Return a set of all connected minion ids, optionally within a subset
        """
        if include_localhost is not None:
            salt.utils.versions.warn_until(
                "Sodium",
                "The 'include_localhost' argument is no longer required; any"
                "connected localhost minion will always be included.",
            )
        if show_ipv4 is not None:
            salt.utils.versions.warn_until(
                "Sodium",
                "The 'show_ipv4' argument has been renamed to 'show_ip' as"
                "it now also includes IPv6 addresses for IPv6-connected"
                "minions.",
            )
        minions = set()
        if self.opts.get("minion_data_cache", False):
            search = self.cache.list("minions")
            if search is None:
                return minions
            addrs = salt.utils.network.local_port_tcp(int(self.opts["publish_port"]))
            if "127.0.0.1" in addrs:
                # Add in the address of a possible locally-connected minion.
                addrs.discard("127.0.0.1")
                addrs.update(set(salt.utils.network.ip_addrs(include_loopback=False)))
            if "::1" in addrs:
                # Add in the address of a possible locally-connected minion.
                addrs.discard("::1")
                addrs.update(set(salt.utils.network.ip_addrs6(include_loopback=False)))
            if subset:
                search = subset
            for id_ in search:
                try:
                    mdata = self.cache.fetch("minions/{0}".format(id_), "data")
                except SaltCacheError:
                    # If a SaltCacheError is explicitly raised during the fetch operation,
                    # permission was denied to open the cached data.p file. Continue on as
                    # in the releases <= 2016.3. (An explicit error raise was added in PR
                    # #35388. See issue #36867 for more information.
                    continue
                if mdata is None:
                    continue
                grains = mdata.get("grains", {})
                for ipv4 in grains.get("ipv4", []):
                    if ipv4 in addrs:
                        if show_ip:
                            minions.add((id_, ipv4))
                        else:
                            minions.add(id_)
                        break
                for ipv6 in grains.get("ipv6", []):
                    if ipv6 in addrs:
                        if show_ip:
                            minions.add((id_, ipv6))
                        else:
                            minions.add(id_)
                        break
        return minions

    def _all_minions(self, expr=None):
        """
        Return a list of all minions that have auth'd
        """
        mlist = []
        for fn_ in salt.utils.data.sorted_ignorecase(
            os.listdir(os.path.join(self.opts["pki_dir"], self.acc))
        ):
            if not fn_.startswith(".") and os.path.isfile(
                os.path.join(self.opts["pki_dir"], self.acc, fn_)
            ):
                mlist.append(fn_)
        return {"minions": mlist, "missing": []}

    def check_minions(
        self, expr, tgt_type="glob", delimiter=DEFAULT_TARGET_DELIM, greedy=True
    ):
        """
        Check the passed regex against the available minions' public keys
        stored for authentication. This should return a set of ids which
        match the regex, this will then be used to parse the returns to
        make sure everyone has checked back in.
        """

        try:
            if expr is None:
                expr = ""
            check_func = getattr(self, "_check_{0}_minions".format(tgt_type), None)
            if tgt_type in (
                "grain",
                "grain_pcre",
                "pillar",
                "pillar_pcre",
                "pillar_exact",
                "compound",
                "compound_pillar_exact",
            ):
                # pylint: disable=not-callable
                _res = check_func(expr, delimiter, greedy)
                # pylint: enable=not-callable
            else:
                _res = check_func(expr, greedy)  # pylint: disable=not-callable
            _res["ssh_minions"] = False
            if self.opts.get("enable_ssh_minions", False) is True and isinstance(
                "tgt", six.string_types
            ):
                roster = salt.roster.Roster(self.opts, self.opts.get("roster", "flat"))
                ssh_minions = roster.targets(expr, tgt_type)
                if ssh_minions:
                    _res["minions"].extend(ssh_minions)
                    _res["ssh_minions"] = True
        except Exception:  # pylint: disable=broad-except
            log.exception(
                "Failed matching available minions with %s pattern: %s", tgt_type, expr
            )
            _res = {"minions": [], "missing": []}
        return _res

    def validate_tgt(self, valid, expr, tgt_type, minions=None, expr_form=None):
        """
        Return a Bool. This function returns if the expression sent in is
        within the scope of the valid expression
        """

        v_minions = set(self.check_minions(valid, "compound").get("minions", []))
        if minions is None:
            _res = self.check_minions(expr, tgt_type)
            minions = set(_res["minions"])
        else:
            minions = set(minions)
        d_bool = not bool(minions.difference(v_minions))
        if len(v_minions) == len(minions) and d_bool:
            return True
        return d_bool

    def match_check(self, regex, fun):
        """
        Validate a single regex to function comparison, the function argument
        can be a list of functions. It is all or nothing for a list of
        functions
        """
        vals = []
        if isinstance(fun, six.string_types):
            fun = [fun]
        for func in fun:
            try:
                if re.match(regex, func):
                    vals.append(True)
                else:
                    vals.append(False)
            except Exception:  # pylint: disable=broad-except
                log.error("Invalid regular expression: %s", regex)
        return vals and all(vals)

    def auth_check_expanded(
        self,
        auth_list,
        funs,
        args,
        tgt,
        tgt_type="glob",
        groups=None,
        publish_validate=False,
    ):

        # Here's my thinking
        # 1. Retrieve anticipated targeted minions
        # 2. Iterate through each entry in the auth_list
        # 3. If it is a minion_id, check to see if any targeted minions match.
        #    If there is a match, check to make sure funs are permitted
        #    (if it's not a match we don't care about this auth entry and can
        #     move on)
        #    a. If funs are permitted, Add this minion_id to a new set of allowed minion_ids
        #       If funs are NOT permitted, can short-circuit and return FALSE
        #    b. At the end of the auth_list loop, make sure all targeted IDs
        #       are in the set of allowed minion_ids.  If not, return FALSE
        # 4. If it is a target (glob, pillar, etc), retrieve matching minions
        #    and make sure that ALL targeted minions are in the set.
        #    then check to see if the funs are permitted
        #    a. If ALL targeted minions are not in the set, then return FALSE
        #    b. If the desired fun doesn't mass the auth check with any
        #       auth_entry's fun, then return FALSE

        # NOTE we are not going to try to allow functions to run on partial
        # sets of minions.  If a user targets a group of minions and does not
        # have access to run a job on ALL of these minions then the job will
        # fail with 'Eauth Failed'.

        # The recommended workflow in that case will be for the user to narrow
        # his target.

        # This should cover adding the AD LDAP lookup functionality while
        # preserving the existing auth behavior.

        # Recommend we config-get this behind an entry called
        # auth.enable_expanded_auth_matching
        # and default to False
        v_tgt_type = tgt_type
        if tgt_type.lower() in ("pillar", "pillar_pcre"):
            v_tgt_type = "pillar_exact"
        elif tgt_type.lower() == "compound":
            v_tgt_type = "compound_pillar_exact"
        _res = self.check_minions(tgt, v_tgt_type)
        v_minions = set(_res["minions"])

        _res = self.check_minions(tgt, tgt_type)
        minions = set(_res["minions"])

        mismatch = bool(minions.difference(v_minions))
        # If the non-exact match gets more minions than the exact match
        # then pillar globbing or PCRE is being used, and we have a
        # problem
        if publish_validate:
            if mismatch:
                return False
        # compound commands will come in a list so treat everything as a list
        if not isinstance(funs, list):
            funs = [funs]
            args = [args]

        # Take the auth list and get all the minion names inside it
        allowed_minions = set()

        auth_dictionary = {}

        # Make a set, so we are guaranteed to have only one of each minion
        # Also iterate through the entire auth_list and create a dictionary
        # so it's easy to look up what functions are permitted
        for auth_list_entry in auth_list:
            if isinstance(auth_list_entry, six.string_types):
                for fun in funs:
                    # represents toplevel auth entry is a function.
                    # so this fn is permitted by all minions
                    if self.match_check(auth_list_entry, fun):
                        return True
                continue
            if isinstance(auth_list_entry, dict):
                if len(auth_list_entry) != 1:
                    log.info("Malformed ACL: %s", auth_list_entry)
                    continue
            allowed_minions.update(set(auth_list_entry.keys()))
            for key in auth_list_entry:
                for match in set(self.check_minions(key, "compound")):
                    if match in auth_dictionary:
                        auth_dictionary[match].extend(auth_list_entry[key])
                    else:
                        auth_dictionary[match] = auth_list_entry[key]

        allowed_minions_from_auth_list = set()
        for next_entry in allowed_minions:
            allowed_minions_from_auth_list.update(
                set(self.check_minions(next_entry, "compound"))
            )
        # 'minions' here are all the names of minions matched by the target
        # if we take out all the allowed minions, and there are any left, then
        # the target includes minions that are not allowed by eauth
        # so we can give up here.
        if len(minions - allowed_minions_from_auth_list) > 0:
            return False

        try:
            for minion in minions:
                results = []
                for num, fun in enumerate(auth_dictionary[minion]):
                    results.append(self.match_check(fun, funs))
                if not any(results):
                    return False
            return True

        except TypeError:
            return False
        return False

    def auth_check(
        self,
        auth_list,
        funs,
        args,
        tgt,
        tgt_type="glob",
        groups=None,
        publish_validate=False,
        minions=None,
        whitelist=None,
    ):
        """
        Returns a bool which defines if the requested function is authorized.
        Used to evaluate the standard structure under external master
        authentication interfaces, like eauth, peer, peer_run, etc.
        """
        if self.opts.get("auth.enable_expanded_auth_matching", False):
            return self.auth_check_expanded(
                auth_list, funs, args, tgt, tgt_type, groups, publish_validate
            )
        if publish_validate:
            v_tgt_type = tgt_type
            if tgt_type.lower() in ("pillar", "pillar_pcre"):
                v_tgt_type = "pillar_exact"
            elif tgt_type.lower() == "compound":
                v_tgt_type = "compound_pillar_exact"
            _res = self.check_minions(tgt, v_tgt_type)
            v_minions = set(_res["minions"])

            _res = self.check_minions(tgt, tgt_type)
            minions = set(_res["minions"])

            mismatch = bool(minions.difference(v_minions))
            # If the non-exact match gets more minions than the exact match
            # then pillar globbing or PCRE is being used, and we have a
            # problem
            if mismatch:
                return False
        # compound commands will come in a list so treat everything as a list
        if not isinstance(funs, list):
            funs = [funs]
            args = [args]
        try:
            for num, fun in enumerate(funs):
                if whitelist and fun in whitelist:
                    return True
                for ind in auth_list:
                    if isinstance(ind, six.string_types):
                        # Allowed for all minions
                        if self.match_check(ind, fun):
                            return True
                    elif isinstance(ind, dict):
                        if len(ind) != 1:
                            # Invalid argument
                            continue
                        valid = next(six.iterkeys(ind))
                        # Check if minions are allowed
                        if self.validate_tgt(valid, tgt, tgt_type, minions=minions):
                            # Minions are allowed, verify function in allowed list
                            fun_args = args[num]
                            fun_kwargs = fun_args[-1] if fun_args else None
                            if (
                                isinstance(fun_kwargs, dict)
                                and "__kwarg__" in fun_kwargs
                            ):
                                fun_args = list(fun_args)  # copy on modify
                                del fun_args[-1]
                            else:
                                fun_kwargs = None
                            if self.__fun_check(ind[valid], fun, fun_args, fun_kwargs):
                                return True
        except TypeError:
            return False
        return False

    def fill_auth_list_from_groups(self, auth_provider, user_groups, auth_list):
        """
        Returns a list of authorisation matchers that a user is eligible for.
        This list is a combination of the provided personal matchers plus the
        matchers of any group the user is in.
        """
        group_names = [item for item in auth_provider if item.endswith("%")]
        if group_names:
            for group_name in group_names:
                if group_name.rstrip("%") in user_groups:
                    for matcher in auth_provider[group_name]:
                        auth_list.append(matcher)
        return auth_list

    def fill_auth_list(
        self, auth_provider, name, groups, auth_list=None, permissive=None
    ):
        """
        Returns a list of authorisation matchers that a user is eligible for.
        This list is a combination of the provided personal matchers plus the
        matchers of any group the user is in.
        """
        if auth_list is None:
            auth_list = []
        if permissive is None:
            permissive = self.opts.get("permissive_acl")
        name_matched = False
        for match in auth_provider:
            if match == "*" and not permissive:
                continue
            if match.endswith("%"):
                if match.rstrip("%") in groups:
                    auth_list.extend(auth_provider[match])
            else:
                if salt.utils.stringutils.expr_match(match, name):
                    name_matched = True
                    auth_list.extend(auth_provider[match])
        if not permissive and not name_matched and "*" in auth_provider:
            auth_list.extend(auth_provider["*"])
        return auth_list

    def wheel_check(self, auth_list, fun, args):
        """
        Check special API permissions
        """
        return self.spec_check(auth_list, fun, args, "wheel")

    def runner_check(self, auth_list, fun, args):
        """
        Check special API permissions
        """
        return self.spec_check(auth_list, fun, args, "runner")

    def spec_check(self, auth_list, fun, args, form):
        """
        Check special API permissions
        """
        if not auth_list:
            return False
        if form != "cloud":
            comps = fun.split(".")
            if len(comps) != 2:
                # Hint at a syntax error when command is passed improperly,
                # rather than returning an authentication error of some kind.
                # See Issue #21969 for more information.
                return {
                    "error": {
                        "name": "SaltInvocationError",
                        "message": "A command invocation error occurred: Check syntax.",
                    }
                }
            mod_name = comps[0]
            fun_name = comps[1]
        else:
            fun_name = mod_name = fun
        for ind in auth_list:
            if isinstance(ind, six.string_types):
                if ind[0] == "@":
                    if (
                        ind[1:] == mod_name
                        or ind[1:] == form
                        or ind == "@{0}s".format(form)
                    ):
                        return True
            elif isinstance(ind, dict):
                if len(ind) != 1:
                    continue
                valid = next(six.iterkeys(ind))
                if valid[0] == "@":
                    if valid[1:] == mod_name:
                        if self.__fun_check(
                            ind[valid], fun_name, args.get("arg"), args.get("kwarg")
                        ):
                            return True
                    if valid[1:] == form or valid == "@{0}s".format(form):
                        if self.__fun_check(
                            ind[valid], fun, args.get("arg"), args.get("kwarg")
                        ):
                            return True
        return False

    def __fun_check(self, valid, fun, args=None, kwargs=None):
        """
        Check the given function name (fun) and its arguments (args) against the list of conditions.
        """
        if not isinstance(valid, list):
            valid = [valid]
        for cond in valid:
            # Function name match
            if isinstance(cond, six.string_types):
                if self.match_check(cond, fun):
                    return True
            # Function and args match
            elif isinstance(cond, dict):
                if len(cond) != 1:
                    # Invalid argument
                    continue
                fname_cond = next(six.iterkeys(cond))
                if self.match_check(
                    fname_cond, fun
                ):  # check key that is function name match
                    if self.__args_check(cond[fname_cond], args, kwargs):
                        return True
        return False

    def __args_check(self, valid, args=None, kwargs=None):
        """
        valid is a dicts: {'args': [...], 'kwargs': {...}} or a list of such dicts.
        """
        if not isinstance(valid, list):
            valid = [valid]
        for cond in valid:
            if not isinstance(cond, dict):
                # Invalid argument
                continue
            # whitelist args, kwargs
            cond_args = cond.get("args", [])
            good = True
            for i, cond_arg in enumerate(cond_args):
                if args is None or len(args) <= i:
                    good = False
                    break
                if cond_arg is None:  # None == '.*' i.e. allow any
                    continue
                if not self.match_check(cond_arg, six.text_type(args[i])):
                    good = False
                    break
            if not good:
                continue
            # Check kwargs
            cond_kwargs = cond.get("kwargs", {})
            for k, v in six.iteritems(cond_kwargs):
                if kwargs is None or k not in kwargs:
                    good = False
                    break
                if v is None:  # None == '.*' i.e. allow any
                    continue
                if not self.match_check(v, six.text_type(kwargs[k])):
                    good = False
                    break
            if good:
                return True
        return False
