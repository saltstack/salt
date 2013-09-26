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

log = logging.getLogger(__name__)


def nodegroup_comp(group, nodegroups, skip=None):
    '''
    Take the nodegroup and the nodegroups and fill in nodegroup refs
    '''
    if skip is None:
        skip = set([group])
    if group not in nodegroups:
        return ''
    gstr = nodegroups[group]
    ret = ''
    for comp in gstr.split():
        if not comp.startswith('N@'):
            ret += '{0} '.format(comp)
            continue
        ngroup = comp[2:]
        if ngroup in skip:
            continue
        skip.add(ngroup)
        ret += nodegroup_comp(ngroup, nodegroups, skip)
    return ret


class CkMinions(object):
    '''
    Used to check what minions should respond from a target
    '''
    def __init__(self, opts):
        self.opts = opts
        self.serial = salt.payload.Serial(opts)

    def _check_glob_minions(self, expr):
        '''
        Return the minions found by looking via globs
        '''
        cwd = os.getcwd()
        os.chdir(os.path.join(self.opts['pki_dir'], 'minions'))
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
        ret = []
        for fn_ in os.listdir(os.path.join(self.opts['pki_dir'], 'minions')):
            if fn_ in expr:
                if fn_ not in ret:
                    ret.append(fn_)
        return ret

    def _check_pcre_minions(self, expr):
        '''
        Return the minions found by looking via regular expressions
        '''
        cwd = os.getcwd()
        os.chdir(os.path.join(self.opts['pki_dir'], 'minions'))
        reg = re.compile(expr)
        ret = [fn_ for fn_ in os.listdir('.') if reg.match(fn_)]
        os.chdir(cwd)
        return ret

    def _check_grain_minions(self, expr):
        '''
        Return the minions found by looking via grains
        '''
        minions = set(
            os.listdir(os.path.join(self.opts['pki_dir'], 'minions'))
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
                    salt.utils.fopen(datap)
                ).get('grains')
                if not salt.utils.subdict_match(grains, expr):
                    minions.remove(id_)
        return list(minions)

    def _check_grain_pcre_minions(self, expr):
        '''
        Return the minions found by looking via grains with PCRE
        '''
        minions = set(
            os.listdir(os.path.join(self.opts['pki_dir'], 'minions'))
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
                    salt.utils.fopen(datap)
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
            os.listdir(os.path.join(self.opts['pki_dir'], 'minions'))
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
                    salt.utils.fopen(datap)
                ).get('pillar')
                if not salt.utils.subdict_match(pillar, expr):
                    minions.remove(id_)
        return list(minions)

    def _check_ipcidr_minions(self, expr):
        '''
        Return the minions found by looking via ipcidr
        '''
        minions = set(
            os.listdir(os.path.join(self.opts['pki_dir'], 'minions'))
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
                    salt.utils.fopen(datap)
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
                        if not expr in grains.get('ipv4', []):
                            minions.remove(id_)
        return list(minions)

    def _check_compound_minions(self, expr):
        '''
        Return the minions found by looking via compound matcher
        '''
        minions = set(
            os.listdir(os.path.join(self.opts['pki_dir'], 'minions'))
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
                return list(eval(results))
            except Exception:
                log.error('Invalid compound target: {0}'.format(expr))
                return []
        return list(minions)

    def _all_minions(self, expr=None):
        '''
        Return a list of all minions that have auth'd
        '''
        return os.listdir(os.path.join(self.opts['pki_dir'], 'minions'))

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
                       }[expr_form](expr)
        except Exception:
            log.exception(
                    'Failed matching available minions with {0} pattern: {1}'
                    .format(expr_form, expr))
            minions = expr
        return minions

    def validate_tgt(self, valid, expr, expr_form):
        '''
        Return a Bool. This function returns if the expression sent in is
        within the scope of the valid expression
        '''
        ref = {'G': 'grain',
               'P': 'grain_pcre',
               'X': 'exsel',
               'I': 'pillar',
               'L': 'list',
               'S': 'ipcidr',
               'E': 'pcre',
               'N': 'node'}
        infinite = [
                'node',
                'ipcidr',
                'exsel',
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

    def auth_check(self, auth_list, funs, tgt, tgt_type='glob'):
        '''
        Returns a bool which defines if the requested function is authorized.
        Used to evaluate the standard structure under external master
        authentication interfaces, like eauth, peer, peer_run, etc.
        '''
        # compound commands will come in a list so treat everything as a list
        if not isinstance(funs, list):
            funs = [funs]

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
        return False

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
