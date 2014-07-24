# -*- coding: utf-8 -*-
'''
This module contains routines used to verify the matcher against the minions
expected to return
'''

# Import python libs
import os
import glob
import re
import logging

# Import salt libs
import salt.payload
import salt.utils
from salt.exceptions import CommandExecutionError

HAS_RANGE = False
try:
    import seco.range
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
                if not os.path.isfile(datap):
                    continue
                miniondata = serial.load(salt.utils.fopen(datap, 'rb'))
                grains = miniondata.get('grains')
                pillar = miniondata.get('pillar')
                return id_, grains, pillar
        else:
            # Search for specific minion
            datap = os.path.join(cdir, minion, 'data.p')
            if not os.path.isfile(datap):
                return minion, None, None
            miniondata = serial.load(salt.utils.fopen(datap, 'rb'))
            grains = miniondata.get('grains')
            pillar = miniondata.get('pillar')
            return minion, grains, pillar
    # No cache dir, return empty dict
    return minion if minion else None, None, None


def nodegroup_comp(group, nodegroups, skip=None):
    '''
    Take the nodegroup and the nodegroups and fill in nodegroup refs
    '''
    k = 1
    if skip is None:
        skip = set([group])
        k = 0
    if group not in nodegroups:
        return ''
    gstr = nodegroups[group]
    ret = ''
    for comp in gstr.split(','):
        if not comp.startswith('N@'):
            ret += '{0} or '.format(comp)
            continue
        ngroup = comp[2:]
        if ngroup in skip:
            continue
        skip.add(ngroup)
        ret += nodegroup_comp(ngroup, nodegroups, skip)
    if k == 1:
        return ret
    else:
        return ret[:-3]


class CkMinions(object):
    '''
    Used to check what minions should respond from a target
    '''
    def __init__(self, opts):
        self.opts = opts
        self.serial = salt.payload.Serial(opts)
        if self.opts['transport'] == 'zeromq':
            self.acc = 'minions'
        else:
            self.acc = 'accepted'

    def _check_glob_minions(self, expr):
        '''
        Return the minions found by looking via globs
        '''
        cwd = os.getcwd()
        pki_dir = os.path.join(self.opts['pki_dir'], self.acc)

        # If there is no directory return an empty list
        if os.path.isdir(pki_dir) is False:
            return []

        os.chdir(pki_dir)
        ret = set(glob.glob(expr))
        try:
            os.chdir(cwd)
        except OSError as exc:
            if exc.errno != 13:
                # If it's not a permission denied, perhaps we're running with
                # sudo
                raise
        return list(ret)

    def _check_list_minions(self, expr):
        '''
        Return the minions found by looking via a list
        '''
        if isinstance(expr, str):
            expr = [m for m in expr.split(',') if m]
        ret = []
        for fn_ in os.listdir(os.path.join(self.opts['pki_dir'], self.acc)):
            if fn_ in expr:
                if fn_ not in ret:
                    ret.append(fn_)
        return ret

    def _check_pcre_minions(self, expr):
        '''
        Return the minions found by looking via regular expressions
        '''
        cwd = os.getcwd()
        os.chdir(os.path.join(self.opts['pki_dir'], self.acc))
        reg = re.compile(expr)
        ret = [fn_ for fn_ in os.listdir('.') if reg.match(fn_)]
        os.chdir(cwd)
        return ret

    def _check_grain_minions(self, expr):
        '''
        Return the minions found by looking via grains
        '''
        minions = set(
            os.listdir(os.path.join(self.opts['pki_dir'], self.acc))
        )
        if self.opts.get('minion_data_cache', False):
            cdir = os.path.join(self.opts['cachedir'], 'minions')
            if not os.path.isdir(cdir):
                return list(minions)
            for id_ in os.listdir(cdir):
                if id_ not in minions:
                    continue
                datap = os.path.join(cdir, id_, 'data.p')
                if not os.path.isfile(datap):
                    continue
                grains = self.serial.load(
                    salt.utils.fopen(datap, 'rb')
                ).get('grains')
                if not salt.utils.subdict_match(grains, expr):
                    minions.remove(id_)
        return list(minions)

    def _check_grain_pcre_minions(self, expr):
        '''
        Return the minions found by looking via grains with PCRE
        '''
        minions = set(
            os.listdir(os.path.join(self.opts['pki_dir'], self.acc))
        )
        if self.opts.get('minion_data_cache', False):
            cdir = os.path.join(self.opts['cachedir'], 'minions')
            if not os.path.isdir(cdir):
                return list(minions)
            for id_ in os.listdir(cdir):
                if id_ not in minions:
                    continue
                datap = os.path.join(cdir, id_, 'data.p')
                if not os.path.isfile(datap):
                    continue
                grains = self.serial.load(
                    salt.utils.fopen(datap, 'rb')
                ).get('grains')
                if not salt.utils.subdict_match(grains, expr,
                                                delim=':', regex_match=True):
                    minions.remove(id_)
        return list(minions)

    def _check_pillar_minions(self, expr):
        '''
        Return the minions found by looking via pillar
        '''
        minions = set(
            os.listdir(os.path.join(self.opts['pki_dir'], self.acc))
        )
        if self.opts.get('minion_data_cache', False):
            cdir = os.path.join(self.opts['cachedir'], 'minions')
            if not os.path.isdir(cdir):
                return list(minions)
            for id_ in os.listdir(cdir):
                if id_ not in minions:
                    continue
                datap = os.path.join(cdir, id_, 'data.p')
                if not os.path.isfile(datap):
                    continue
                pillar = self.serial.load(
                    salt.utils.fopen(datap, 'rb')
                ).get('pillar')
                if not salt.utils.subdict_match(pillar, expr):
                    minions.remove(id_)
        return list(minions)

    def _check_ipcidr_minions(self, expr):
        '''
        Return the minions found by looking via ipcidr
        '''
        minions = set(
            os.listdir(os.path.join(self.opts['pki_dir'], self.acc))
        )
        if self.opts.get('minion_data_cache', False):
            cdir = os.path.join(self.opts['cachedir'], 'minions')
            if not os.path.isdir(cdir):
                return list(minions)
            for id_ in os.listdir(cdir):
                if id_ not in minions:
                    continue
                datap = os.path.join(cdir, id_, 'data.p')
                if not os.path.isfile(datap):
                    continue
                grains = self.serial.load(
                    salt.utils.fopen(datap, 'rb')
                ).get('grains')

                num_parts = len(expr.split('/'))
                if num_parts > 2:
                    # Target is not valid CIDR, no minions match
                    return []
                elif num_parts == 2:
                    # Target is CIDR
                    if not salt.utils.network.in_subnet(
                            expr,
                            addrs=grains.get('ipv4', [])):
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
                        if expr not in grains.get('ipv4', []):
                            minions.remove(id_)
        return list(minions)

    def _check_range_minions(self, expr):
        '''
        Return the minions found by looking via range expression
        '''
        if not HAS_RANGE:
            raise CommandExecutionError(
                'Range matcher unavailble (unable to import seco.range, '
                'module most likely not installed)'
            )
        minions = set(
            os.listdir(os.path.join(self.opts['pki_dir'], self.acc))
        )
        if self.opts.get('minion_data_cache', False):
            cdir = os.path.join(self.opts['cachedir'], 'minions')
            if not os.path.isdir(cdir):
                return list(minions)
            for id_ in os.listdir(cdir):
                if id_ not in minions:
                    continue
                datap = os.path.join(cdir, id_, 'data.p')
                if not os.path.isfile(datap):
                    continue
                grains = self.serial.load(
                    salt.utils.fopen(datap, 'rb')
                ).get('grains')

                range_ = seco.range.Range(self.opts['range_server'])
                try:
                    if grains.get('fqdn', '') not in range_.expand(expr):
                        minions.remove(id_)
                except seco.range.RangeException as exc:
                    log.debug(
                        'Range exception in compound match: {0}'.format(exc)
                    )
                    minions.remove(id_)
        return list(minions)

    def _check_compound_minions(self, expr):
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
                   'L': self._check_list_minions,
                   'S': self._check_ipcidr_minions,
                   'E': self._check_pcre_minions,
                   'R': self._all_minions}
            results = []
            unmatched = []
            opers = ['and', 'or', 'not', '(', ')']
            tokens = expr.split()
            for match in tokens:
                # Try to match tokens from the compound target, first by using
                # the 'G, X, I, L, S, E' matcher types, then by hostname glob.
                if '@' in match and match[1] == '@':
                    comps = match.split('@')
                    matcher = ref.get(comps[0])
                    if not matcher:
                        # If an unknown matcher is called at any time, fail out
                        return []
                    if unmatched and unmatched[-1] == '-':
                        results.append(str(set(matcher('@'.join(comps[1:])))))
                        results.append(')')
                        unmatched.pop()
                    else:
                        results.append(str(set(matcher('@'.join(comps[1:])))))
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
                                str(set(self._check_glob_minions(match))))
                        results.append(')')
                        unmatched.pop()
                    else:
                        results.append(
                                str(set(self._check_glob_minions(match))))
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
                if not os.path.isfile(datap):
                    continue
                try:
                    grains = self.serial.load(
                        salt.utils.fopen(datap, 'rb')
                    ).get('grains', {})
                except AttributeError:
                    pass
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

    def check_minions(self, expr, expr_form='glob'):
        '''
        Check the passed regex against the available minions' public keys
        stored for authentication. This should return a set of ids which
        match the regex, this will then be used to parse the returns to
        make sure everyone has checked back in.
        '''
        try:
            minions = {'glob': self._check_glob_minions,
                       'pcre': self._check_pcre_minions,
                       'list': self._check_list_minions,
                       'grain': self._check_grain_minions,
                       'grain_pcre': self._check_grain_pcre_minions,
                       'pillar': self._check_pillar_minions,
                       'compound': self._check_compound_minions,
                       'ipcidr': self._check_ipcidr_minions,
                       'range': self._check_range_minions,
                       }[expr_form](expr)
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
               'L': 'list',
               'S': 'ipcidr',
               'E': 'pcre',
               'N': 'node'}
        infinite = [
                'node',
                'ipcidr',
                'pillar']
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

    def auth_check(self, auth_list, funs, tgt, tgt_type='glob', groups=None):
        '''
        Returns a bool which defines if the requested function is authorized.
        Used to evaluate the standard structure under external master
        authentication interfaces, like eauth, peer, peer_run, etc.
        '''
        # compound commands will come in a list so treat everything as a list
        if not isinstance(funs, list):
            funs = [funs]
        try:
            for fun in funs:
                for ind in auth_list:
                    if isinstance(ind, str):
                        # Allowed for all minions
                        if self.match_check(ind, fun):
                            return True
                    elif isinstance(ind, dict):
                        if len(ind) != 1:
                            # Invalid argument
                            continue
                        valid = ind.keys()[0]
                        # Check if minions are allowed
                        if self.validate_tgt(
                                valid,
                                tgt,
                                tgt_type):
                            # Minions are allowed, verify function in allowed list
                            if isinstance(ind[valid], str):
                                if self.match_check(ind[valid], fun):
                                    return True
                            elif isinstance(ind[valid], list):
                                for regex in ind[valid]:
                                    if self.match_check(regex, fun):
                                        return True
        except TypeError:
            return False
        return False

    def gather_groups(self, auth_provider, user_groups, auth_list):
        '''
        Returns the list of groups, if any, for a given authentication provider type

        Groups are defined as any dict in which a key has a trailing '%'
        '''
        group_perm_keys = filter(lambda(item): item.endswith('%'), auth_provider)
        groups = {}
        if group_perm_keys:
            for group_perm in group_perm_keys:
                for matcher in auth_provider[group_perm]:
                    if group_perm[:-1] in user_groups:
                        groups[group_perm] = matcher
        else:
            return None
        for item in groups.values():
            auth_list.append(item)
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
            if isinstance(ind, str):
                if ind.startswith('@') and ind[1:] == mod:
                    return True
                if ind == '@wheel':
                    return True
                if ind == '@wheels':
                    return True
            elif isinstance(ind, dict):
                if len(ind) != 1:
                    continue
                valid = ind.keys()[0]
                if valid.startswith('@') and valid[1:] == mod:
                    if isinstance(ind[valid], str):
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
            if isinstance(ind, str):
                if ind.startswith('@') and ind[1:] == mod:
                    return True
                if ind == '@runners':
                    return True
                if ind == '@runner':
                    return True
            elif isinstance(ind, dict):
                if len(ind) != 1:
                    continue
                valid = ind.keys()[0]
                if valid.startswith('@') and valid[1:] == mod:
                    if isinstance(ind[valid], str):
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
            if isinstance(ind, str):
                if ind.startswith('@') and ind[1:] == mod:
                    return True
                if ind == '@{0}'.format(form):
                    return True
                if ind == '@{0}s'.format(form):
                    return True
            elif isinstance(ind, dict):
                if len(ind) != 1:
                    continue
                valid = ind.keys()[0]
                if valid.startswith('@') and valid[1:] == mod:
                    if isinstance(ind[valid], str):
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
