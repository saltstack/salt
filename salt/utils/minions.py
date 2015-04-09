# -*- coding: utf-8 -*-
'''
This module contains routines used to verify the matcher against the minions
expected to return
'''

from __future__ import absolute_import

# Import python libs
import os
import fnmatch
import re
import logging

# Import salt libs
import salt.payload
import salt.utils
from salt.defaults import DEFAULT_TARGET_DELIM
from salt.exceptions import CommandExecutionError
from salt._compat import string_types

HAS_RANGE = False
try:
    import seco.range  # pylint: disable=import-error
    HAS_RANGE = True
except ImportError:
    pass

log = logging.getLogger(__name__)


def get_minion_data(minion, opts):
    '''
    Get the grains/pillar for a specific minion.  If minion is None, it
    will return the grains/pillar for the first minion it finds.

    Return value is a tuple of the minion ID, grains, and pillar
    '''
    if opts.get('minion_data_cache', False):
        serial = salt.payload.Serial(opts)
        cdir = os.path.join(opts['cachedir'], 'minions')
        if not os.path.isdir(cdir):
            return minion if minion else None, None, None
        minions = os.listdir(cdir)
        if minion is None:
            # If no minion specified, take first one with valid grains
            for id_ in minions:
                datap = os.path.join(cdir, id_, 'data.p')
                try:
                    with salt.utils.fopen(datap, 'rb') as fp_:
                        miniondata = serial.load(fp_)
                except (IOError, OSError):
                    continue
                grains = miniondata.get('grains')
                pillar = miniondata.get('pillar')
                return id_, grains, pillar
        else:
            # Search for specific minion
            datap = os.path.join(cdir, minion, 'data.p')
            try:
                with salt.utils.fopen(datap, 'rb') as fp_:
                    miniondata = serial.load(fp_)
            except (IOError, OSError):
                return minion, None, None
            grains = miniondata.get('grains')
            pillar = miniondata.get('pillar')
            return minion, grains, pillar
    # No cache dir, return empty dict
    return minion if minion else None, None, None


def nodegroup_comp(nodegroup, nodegroups, skip=None):
    '''
    Recursively expand ``nodegroup`` from ``nodegroups``; ignore nodegroups in ``skip``
    '''

    if skip is None:
        skip = set()
    elif nodegroup in skip:
        log.error('Failed nodegroup expansion: illegal nested nodegroup "{0}"'.format(nodegroup))
        return ''

    skip.add(nodegroup)

    if nodegroup not in nodegroups:
        log.error('Failed nodegroup expansion: unknown nodegroup "{0}"'.format(nodegroup))
        return ''

    nglookup = nodegroups[nodegroup]

    ret = []
    opers = ['and', 'or', 'not', '(', ')']
    tokens = nglookup.split()
    for match in tokens:
        if match in opers:
            ret.append(match)
        elif len(match) >= 3 and match[:2] == 'N@':
            ret.append(nodegroup_comp(match[2:], nodegroups, skip=skip))
        else:
            ret.append(match)

    expanded = '( {0} )'.format(' '.join(ret)) if ret else ''
    log.debug('nodegroup_comp("{0}") => {1}'.format(nodegroup, expanded))
    return expanded


class CkMinions(object):
    '''
    Used to check what minions should respond from a target

    Note: This is a best-effort set of the minions that would match a target.
    Depending on master configuration (grains caching, etc.) and topology (syndics)
    the list may be a subset-- but we err on the side of too-many minions in this
    class.
    '''
    def __init__(self, opts):
        self.opts = opts
        self.serial = salt.payload.Serial(opts)
        if self.opts['transport'] == 'zeromq':
            self.acc = 'minions'
        else:
            self.acc = 'accepted'

    def _check_glob_minions(self, expr, greedy):  # pylint: disable=unused-argument
        '''
        Return the minions found by looking via globs
        '''
        pki_dir = os.path.join(self.opts['pki_dir'], self.acc)
        try:
            files = os.listdir(pki_dir)
            return fnmatch.filter(files, expr)
        except OSError:
            return []

    def _check_list_minions(self, expr, greedy):  # pylint: disable=unused-argument
        '''
        Return the minions found by looking via a list
        '''
        if isinstance(expr, string_types):
            expr = [m for m in expr.split(',') if m]
        ret = []
        for m in expr:
            if os.path.isfile(os.path.join(self.opts['pki_dir'], self.acc, m)):
                ret.append(m)
        return ret

    def _check_pcre_minions(self, expr, greedy):  # pylint: disable=unused-argument
        '''
        Return the minions found by looking via regular expressions
        '''
        try:
            minions = os.listdir(os.path.join(self.opts['pki_dir'], self.acc))
            reg = re.compile(expr)
            return [m for m in minions if reg.match(m)]
        except OSError:
            return []

    def _check_cache_minions(self,
                             expr,
                             delimiter,
                             greedy,
                             search_type,
                             regex_match=False,
                             exact_match=False):
        '''
        Helper function to search for minions in master caches
        '''
        cache_enabled = self.opts.get('minion_data_cache', False)

        if greedy:
            minions = set(
                os.listdir(os.path.join(self.opts['pki_dir'], self.acc))
            )
        elif cache_enabled:
            minions = os.listdir(os.path.join(self.opts['cachedir'], 'minions'))
        else:
            return list()

        if cache_enabled:
            cdir = os.path.join(self.opts['cachedir'], 'minions')
            if not os.path.isdir(cdir):
                return list(minions)
            for id_ in os.listdir(cdir):
                if not greedy and id_ not in minions:
                    continue
                datap = os.path.join(cdir, id_, 'data.p')
                if not os.path.isfile(datap):
                    if not greedy and id_ in minions:
                        minions.remove(id_)
                    continue
                search_results = self.serial.load(
                    salt.utils.fopen(datap, 'rb')
                ).get(search_type)
                if not salt.utils.subdict_match(search_results,
                                                expr,
                                                regex_match=regex_match,
                                                exact_match=exact_match) and id_ in minions:
                    minions.remove(id_)
        return list(minions)

    def _check_grain_minions(self, expr, delimiter, greedy):
        '''
        Return the minions found by looking via grains
        '''
        return self._check_cache_minions(expr, delimiter, greedy, 'grains')

    def _check_grain_pcre_minions(self, expr, delimiter, greedy):
        '''
        Return the minions found by looking via grains with PCRE
        '''
        return self._check_cache_minions(expr,
                                         delimiter,
                                         greedy,
                                         'grains',
                                         regex_match=True)

    def _check_pillar_minions(self, expr, delimiter, greedy):
        '''
        Return the minions found by looking via pillar
        '''
        return self._check_cache_minions(expr, delimiter, greedy, 'pillar')

    def _check_pillar_pcre_minions(self, expr, delimiter, greedy):
        '''
        Return the minions found by looking via pillar with PCRE
        '''
        return self._check_cache_minions(expr,
                                         delimiter,
                                         greedy,
                                         'pillar',
                                         regex_match=True)

    def _check_pillar_exact_minions(self, expr, delimiter, greedy):
        '''
        Return the minions found by looking via pillar
        '''
        return self._check_cache_minions(expr,
                                         delimiter,
                                         greedy,
                                         'pillar',
                                         exact_match=True)

    def _check_ipcidr_minions(self, expr, greedy):
        '''
        Return the minions found by looking via ipcidr
        '''
        cache_enabled = self.opts.get('minion_data_cache', False)

        if greedy:
            minions = set(
                os.listdir(os.path.join(self.opts['pki_dir'], self.acc))
            )
        elif cache_enabled:
            minions = os.listdir(os.path.join(self.opts['cachedir'], 'minions'))
        else:
            return list()

        if cache_enabled:
            cdir = os.path.join(self.opts['cachedir'], 'minions')
            if not os.path.isdir(cdir):
                return list(minions)
            for id_ in os.listdir(cdir):
                if not greedy and id_ not in minions:
                    continue
                datap = os.path.join(cdir, id_, 'data.p')
                if not os.path.isfile(datap):
                    if not greedy and id_ in minions:
                        minions.remove(id_)
                    continue
                try:
                    with salt.utils.fopen(datap, 'rb') as fp_:
                        grains = self.serial.load(fp_).get('grains')
                except (IOError, OSError):
                    continue
                num_parts = len(expr.split('/'))
                if num_parts > 2:
                    # Target is not valid CIDR, no minions match
                    return []
                elif num_parts == 2:
                    # Target is CIDR
                    if not salt.utils.network.in_subnet(
                            expr,
                            addrs=grains.get('ipv4', [])) and id_ in minions:
                        minions.remove(id_)
                else:
                    # Target is an IPv4 address
                    import socket
                    try:
                        socket.inet_aton(expr)
                    except socket.error:
                        # Not a valid IPv4 address, no minions match
                        return []
                    else:
                        if expr not in grains.get('ipv4', []) and id_ in minions:
                            minions.remove(id_)
        return list(minions)

    def _check_range_minions(self, expr, greedy):
        '''
        Return the minions found by looking via range expression
        '''
        if not HAS_RANGE:
            raise CommandExecutionError(
                'Range matcher unavailable (unable to import seco.range, '
                'module most likely not installed)'
            )
        if not hasattr(self, '_range'):
            self._range = seco.range.Range(self.opts['range_server'])
        try:
            return self._range.expand(expr)
        except seco.range.RangeException as exc:
            log.error(
                'Range exception in compound match: {0}'.format(exc)
            )
            cache_enabled = self.opts.get('minion_data_cache', False)
            if greedy:
                return os.listdir(os.path.join(self.opts['pki_dir'], self.acc))
            elif cache_enabled:
                return os.listdir(os.path.join(self.opts['cachedir'], 'minions'))
            else:
                return list()

    def _check_compound_pillar_exact_minions(self, expr, delimiter, greedy):
        '''
        Return the minions found by looking via compound matcher

        Disable pillar glob matching
        '''
        return self._check_compound_minions(expr,
                                            delimiter,
                                            greedy,
                                            pillar_exact=True)

    def _check_compound_minions(self,
                                expr,
                                delimiter,
                                greedy,
                                pillar_exact=False):  # pylint: disable=unused-argument
        '''
        Return the minions found by looking via compound matcher
        '''
        minions = set(
            os.listdir(os.path.join(self.opts['pki_dir'], self.acc))
        )
        if self.opts.get('minion_data_cache', False):
            ref = {'G': self._check_grain_minions,
                   'P': self._check_grain_pcre_minions,
                   'I': self._check_pillar_minions,
                   'J': self._check_pillar_pcre_minions,
                   'L': self._check_list_minions,
                   'S': self._check_ipcidr_minions,
                   'E': self._check_pcre_minions,
                   'R': self._all_minions}
            if pillar_exact:
                ref['I'] = self._check_pillar_exact_minions
                ref['J'] = self._check_pillar_exact_minions
            results = []
            unmatched = []
            opers = ['and', 'or', 'not', '(', ')']
            tokens = expr.split()
            for match in tokens:
                # Try to match tokens from the compound target, first by using
                # the 'G, X, I, J, L, S, E' matcher types, then by hostname glob.
                if '@' in match and match[1] == '@':
                    comps = match.split('@')
                    matcher = ref.get(comps[0])

                    matcher_args = ['@'.join(comps[1:])]
                    if comps[0] in ('G', 'P', 'I', 'J'):
                        matcher_args.append(delimiter)
                    matcher_args.append(True)

                    if not matcher:
                        # If an unknown matcher is called at any time, fail out
                        return []
                    if unmatched and unmatched[-1] == '-':
                        results.append(str(set(matcher(*matcher_args))))
                        results.append(')')
                        unmatched.pop()
                    else:
                        results.append(str(set(matcher(*matcher_args))))
                elif match in opers:
                    # We didn't match a target, so append a boolean operator or
                    # subexpression
                    if results:
                        if match == 'not':
                            if results[-1] == '&':
                                pass
                            elif results[-1] == '|':
                                pass
                            else:
                                results.append('&')
                            results.append('(')
                            results.append(str(set(minions)))
                            results.append('-')
                            unmatched.append('-')
                        elif match == 'and':
                            results.append('&')
                        elif match == 'or':
                            results.append('|')
                        elif match == '(':
                            results.append(match)
                            unmatched.append(match)
                        elif match == ')':
                            if not unmatched or unmatched[-1] != '(':
                                log.error('Invalid compound expr (unexpected '
                                          'right parenthesis): {0}'
                                          .format(expr))
                                return []
                            results.append(match)
                            unmatched.pop()
                            if unmatched and unmatched[-1] == '-':
                                results.append(')')
                                unmatched.pop()
                        else:  # Won't get here, unless oper is added
                            log.error('Unhandled oper in compound expr: {0}'
                                      .format(expr))
                            return []
                    else:
                        # seq start with oper, fail
                        if match == '(':
                            results.append(match)
                            unmatched.append(match)
                        else:
                            return []
                else:
                    # The match is not explicitly defined, evaluate as a glob
                    if unmatched and unmatched[-1] == '-':
                        results.append(
                                str(set(self._check_glob_minions(match, True))))
                        results.append(')')
                        unmatched.pop()
                    else:
                        results.append(
                                str(set(self._check_glob_minions(match, True))))
            for token in unmatched:
                results.append(')')
            results = ' '.join(results)
            log.debug('Evaluating final compound matching expr: {0}'
                      .format(results))
            try:
                return list(eval(results))  # pylint: disable=W0123
            except Exception:
                log.error('Invalid compound target: {0}'.format(expr))
                return []
        return list(minions)

    def connected_ids(self, subset=None, show_ipv4=False):
        '''
        Return a set of all connected minion ids, optionally within a subset
        '''
        minions = set()
        if self.opts.get('minion_data_cache', False):
            cdir = os.path.join(self.opts['cachedir'], 'minions')
            if not os.path.isdir(cdir):
                return minions
            addrs = salt.utils.network.local_port_tcp(int(self.opts['publish_port']))
            if subset:
                search = subset
            else:
                search = os.listdir(cdir)
            for id_ in search:
                datap = os.path.join(cdir, id_, 'data.p')
                try:
                    with salt.utils.fopen(datap, 'rb') as fp_:
                        grains = self.serial.load(fp_).get('grains', {})
                except (AttributeError, IOError, OSError):
                    continue
                for ipv4 in grains.get('ipv4', []):
                    if ipv4 == '127.0.0.1' or ipv4 == '0.0.0.0':
                        continue
                    if ipv4 in addrs:
                        if show_ipv4:
                            minions.add((id_, ipv4))
                        else:
                            minions.add(id_)
                        break
        return minions

    def _all_minions(self, expr=None):
        '''
        Return a list of all minions that have auth'd
        '''
        return os.listdir(os.path.join(self.opts['pki_dir'], self.acc))

    def check_minions(self,
                      expr,
                      expr_form='glob',
                      delimiter=DEFAULT_TARGET_DELIM,
                      greedy=True):
        '''
        Check the passed regex against the available minions' public keys
        stored for authentication. This should return a set of ids which
        match the regex, this will then be used to parse the returns to
        make sure everyone has checked back in.
        '''
        try:
            check_func = getattr(self, '_check_{0}_minions'.format(expr_form), None)
            if expr_form in ('grain',
                             'grain_pcre',
                             'pillar',
                             'pillar_pcre',
                             'pillar_exact',
                             'compound',
                             'compound_pillar_exact'):
                minions = check_func(expr, delimiter, greedy)
            else:
                minions = check_func(expr, greedy)
        except Exception:
            log.exception(
                    'Failed matching available minions with {0} pattern: {1}'
                    .format(expr_form, expr))
            minions = []
        return minions

    def validate_tgt(self, valid, expr, expr_form):
        '''
        Return a Bool. This function returns if the expression sent in is
        within the scope of the valid expression
        '''
        ref = {'G': 'grain',
               'P': 'grain_pcre',
               'I': 'pillar',
               'J': 'pillar_pcre',
               'L': 'list',
               'S': 'ipcidr',
               'E': 'pcre',
               'N': 'node'}
        infinite = [
                'node',
                'ipcidr',
                'pillar',
                'pillar_pcre']
        if not self.opts.get('minion_data_cache', False):
            infinite.append('grain')
            infinite.append('grain_pcre')

        if '@' in valid and valid[1] == '@':
            comps = valid.split('@')
            v_matcher = ref.get(comps[0])
            v_expr = comps[1]
        else:
            v_matcher = 'glob'
            v_expr = valid
        if v_matcher in infinite:
            # We can't be sure what the subset is, only match the identical
            # target
            if v_matcher != expr_form:
                return False
            return v_expr == expr
        v_minions = set(self.check_minions(v_expr, v_matcher))
        minions = set(self.check_minions(expr, expr_form))
        d_bool = not bool(minions.difference(v_minions))
        if len(v_minions) == len(minions) and d_bool:
            return True
        return d_bool

    def match_check(self, regex, fun):
        '''
        Validate a single regex to function comparison, the function argument
        can be a list of functions. It is all or nothing for a list of
        functions
        '''
        vals = []
        if isinstance(fun, str):
            fun = [fun]
        for func in fun:
            try:
                if re.match(regex, func):
                    vals.append(True)
                else:
                    vals.append(False)
            except Exception:
                log.error('Invalid regular expression: {0}'.format(regex))
        return all(vals)

    def any_auth(self, form, auth_list, fun, tgt=None, tgt_type='glob'):
        '''
        Read in the form and determine which auth check routine to execute
        '''
        if form == 'publish':
            return self.auth_check(
                    auth_list,
                    fun,
                    tgt,
                    tgt_type)
        return self.spec_check(
                auth_list,
                fun,
                form)

    def auth_check(self,
                   auth_list,
                   funs,
                   tgt,
                   tgt_type='glob',
                   groups=None,
                   publish_validate=False):
        '''
        Returns a bool which defines if the requested function is authorized.
        Used to evaluate the standard structure under external master
        authentication interfaces, like eauth, peer, peer_run, etc.
        '''
        if publish_validate:
            v_tgt_type = tgt_type
            if tgt_type.lower() in ('pillar', 'pillar_pcre'):
                v_tgt_type = 'pillar_exact'
            elif tgt_type.lower() == 'compound':
                v_tgt_type = 'compound_pillar_exact'
            v_minions = set(self.check_minions(tgt, v_tgt_type))
            minions = set(self.check_minions(tgt, tgt_type))
            mismatch = bool(minions.difference(v_minions))
            # If the non-exact match gets more minions than the exact match
            # then pillar globbing or PCRE is being used, and we have a
            # problem
            if mismatch:
                return False
        # compound commands will come in a list so treat everything as a list
        if not isinstance(funs, list):
            funs = [funs]
        try:
            for fun in funs:
                for ind in auth_list:
                    if isinstance(ind, string_types):
                        # Allowed for all minions
                        if self.match_check(ind, fun):
                            return True
                    elif isinstance(ind, dict):
                        if len(ind) != 1:
                            # Invalid argument
                            continue
                        valid = next(iter(ind.keys()))
                        # Check if minions are allowed
                        if self.validate_tgt(
                                valid,
                                tgt,
                                tgt_type):
                            # Minions are allowed, verify function in allowed list
                            if isinstance(ind[valid], string_types):
                                if self.match_check(ind[valid], fun):
                                    return True
                            elif isinstance(ind[valid], list):
                                for regex in ind[valid]:
                                    if self.match_check(regex, fun):
                                        return True
        except TypeError:
            return False
        return False

    def fill_auth_list_from_groups(self, auth_provider, user_groups, auth_list):
        '''
        Returns a list of authorisation matchers that a user is eligible for.
        This list is a combination of the provided personal matchers plus the
        matchers of any group the user is in.
        '''
        group_names = [item for item in auth_provider if item.endswith('%')]
        if group_names:
            for group_name in group_names:
                if group_name.rstrip("%") in user_groups:
                    for matcher in auth_provider[group_name]:
                        auth_list.append(matcher)
        return auth_list

    def wheel_check(self, auth_list, fun):
        '''
        Check special API permissions
        '''
        comps = fun.split('.')
        if len(comps) != 2:
            return False
        mod = comps[0]
        fun = comps[1]
        for ind in auth_list:
            if isinstance(ind, string_types):
                if ind.startswith('@') and ind[1:] == mod:
                    return True
                if ind == '@wheel':
                    return True
                if ind == '@wheels':
                    return True
            elif isinstance(ind, dict):
                if len(ind) != 1:
                    continue
                valid = next(iter(ind.keys()))
                if valid.startswith('@') and valid[1:] == mod:
                    if isinstance(ind[valid], string_types):
                        if self.match_check(ind[valid], fun):
                            return True
                    elif isinstance(ind[valid], list):
                        for regex in ind[valid]:
                            if self.match_check(regex, fun):
                                return True
        return False

    def runner_check(self, auth_list, fun):
        '''
        Check special API permissions
        '''
        comps = fun.split('.')
        if len(comps) != 2:
            return False
        mod = comps[0]
        fun = comps[1]
        for ind in auth_list:
            if isinstance(ind, string_types):
                if ind.startswith('@') and ind[1:] == mod:
                    return True
                if ind == '@runners':
                    return True
                if ind == '@runner':
                    return True
            elif isinstance(ind, dict):
                if len(ind) != 1:
                    continue
                valid = next(iter(ind.keys()))
                if valid.startswith('@') and valid[1:] == mod:
                    if isinstance(ind[valid], string_types):
                        if self.match_check(ind[valid], fun):
                            return True
                    elif isinstance(ind[valid], list):
                        for regex in ind[valid]:
                            if self.match_check(regex, fun):
                                return True
        return False

    def spec_check(self, auth_list, fun, form):
        '''
        Check special API permissions
        '''
        if form != 'cloud':
            comps = fun.split('.')
            if len(comps) != 2:
                return False
            mod = comps[0]
            fun = comps[1]
        else:
            mod = fun
        for ind in auth_list:
            if isinstance(ind, string_types):
                if ind.startswith('@') and ind[1:] == mod:
                    return True
                if ind == '@{0}'.format(form):
                    return True
                if ind == '@{0}s'.format(form):
                    return True
            elif isinstance(ind, dict):
                if len(ind) != 1:
                    continue
                valid = next(iter(ind.keys()))
                if valid.startswith('@') and valid[1:] == mod:
                    if isinstance(ind[valid], string_types):
                        if self.match_check(ind[valid], fun):
                            return True
                    elif isinstance(ind[valid], list):
                        for regex in ind[valid]:
                            if self.match_check(regex, fun):
                                return True
        return False


def mine_get(tgt, fun, tgt_type='glob', opts=None):
    '''
    Gathers the data from the specified minions' mine, pass in the target,
    function to look up and the target type
    '''
    ret = {}
    serial = salt.payload.Serial(opts)
    checker = salt.utils.minions.CkMinions(opts)
    minions = checker.check_minions(
            tgt,
            tgt_type)
    for minion in minions:
        mine = os.path.join(
                opts['cachedir'],
                'minions',
                minion,
                'mine.p')
        try:
            with salt.utils.fopen(mine, 'rb') as fp_:
                fdata = serial.load(fp_).get(fun)
                if fdata:
                    ret[minion] = fdata
        except Exception:
            continue
    return ret
