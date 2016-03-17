# -*- coding: utf-8 -*-
'''
This module contains routines used to verify the matcher against the minions
expected to return
'''

# Import python libs
from __future__ import absolute_import
import os
import fnmatch
import re
import logging

# Import salt libs
import salt.payload
import salt.utils
from salt.defaults import DEFAULT_TARGET_DELIM
from salt.exceptions import CommandExecutionError
import salt.auth.ldap
import salt.ext.six as six

# Import 3rd-party libs
import salt.ext.six as six
if six.PY3:
    import ipaddress
else:
    import salt.ext.ipaddress as ipaddress
HAS_RANGE = False
try:
    import seco.range  # pylint: disable=import-error
    HAS_RANGE = True
except ImportError:
    pass

log = logging.getLogger(__name__)

TARGET_REX = re.compile(
        r'''(?x)
        (
            (?P<engine>G|P|I|J|L|N|S|E|R)  # Possible target engines
            (?P<delimiter>(?<=G|P|I|J).)?  # Optional delimiter for specific engines
        @)?                                # Engine+delimiter are separated by a '@'
                                           # character and are optional for the target
        (?P<pattern>.+)$'''                # The pattern passed to the target engine
    )


def parse_target(target_expression):
    '''Parse `target_expressing` splitting it into `engine`, `delimiter`,
     `pattern` - returns a dict'''

    match = TARGET_REX.match(target_expression)
    if not match:
        log.warning('Unable to parse target "{0}"'.format(target_expression))
        ret = {
            'engine': None,
            'delimiter': None,
            'pattern': target_expression,
        }
    else:
        ret = match.groupdict()
    return ret


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


def nodegroup_comp(nodegroup, nodegroups, skip=None, first_call=True):
    '''
    Recursively expand ``nodegroup`` from ``nodegroups``; ignore nodegroups in ``skip``

    If a top-level (non-recursive) call finds no nodegroups, return the original
    nodegroup definition (for backwards compatibility). Keep track of recursive
    calls via `first_call` argument
    '''
    expanded_nodegroup = False
    if skip is None:
        skip = set()
    elif nodegroup in skip:
        log.error('Failed nodegroup expansion: illegal nested nodegroup "{0}"'.format(nodegroup))
        return ''

    if nodegroup not in nodegroups:
        log.error('Failed nodegroup expansion: unknown nodegroup "{0}"'.format(nodegroup))
        return ''

    nglookup = nodegroups[nodegroup]
    if isinstance(nglookup, six.string_types):
        words = nglookup.split()
    elif isinstance(nglookup, (list, tuple)):
        words = nglookup
    else:
        log.error(
            'Nodgroup is neither a string, list'
            ' nor tuple: {0} = {1}'.format(nodegroup, nglookup)
        )
        return ''

    skip.add(nodegroup)
    ret = []
    opers = ['and', 'or', 'not', '(', ')']
    for word in words:
        if word in opers:
            ret.append(word)
        elif len(word) >= 3 and word.startswith('N@'):
            expanded_nodegroup = True
            ret.extend(nodegroup_comp(word[2:], nodegroups, skip=skip, first_call=False))
        else:
            ret.append(word)

    if ret:
        ret.insert(0, '(')
        ret.append(')')

    skip.remove(nodegroup)

    log.debug('nodegroup_comp({0}) => {1}'.format(nodegroup, ret))
    # Only return list form if a nodegroup was expanded. Otherwise return
    # the original string to conserve backwards compat
    if expanded_nodegroup or not first_call:
        return ret
    else:
        log.debug('No nested nodegroups detected. '
                  'Using original nodegroup definition: {0}'
                  .format(nodegroups[nodegroup]))
        return nodegroups[nodegroup]


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
        # TODO: this is actually an *auth* check
        if self.opts.get('transport', 'zeromq') in ('zeromq', 'tcp'):
            self.acc = 'minions'
        else:
            self.acc = 'accepted'

    def _check_glob_minions(self, expr, greedy):  # pylint: disable=unused-argument
        '''
        Return the minions found by looking via globs
        '''
        pki_dir = os.path.join(self.opts['pki_dir'], self.acc)
        try:
            files = []
            for fn_ in salt.utils.isorted(os.listdir(pki_dir)):
                if not fn_.startswith('.') and os.path.isfile(os.path.join(pki_dir, fn_)):
                    files.append(fn_)
            return fnmatch.filter(files, expr)
        except OSError:
            return []

    def _check_list_minions(self, expr, greedy):  # pylint: disable=unused-argument
        '''
        Return the minions found by looking via a list
        '''
        if isinstance(expr, six.string_types):
            expr = [m for m in expr.split(',') if m]
        ret = []
        for minion in expr:
            if os.path.isfile(os.path.join(self.opts['pki_dir'], self.acc, minion)):
                ret.append(minion)
        return ret

    def _check_pcre_minions(self, expr, greedy):  # pylint: disable=unused-argument
        '''
        Return the minions found by looking via regular expressions
        '''
        try:
            minions = []
            for fn_ in salt.utils.isorted(os.listdir(os.path.join(self.opts['pki_dir'], self.acc))):
                if not fn_.startswith('.') and os.path.isfile(os.path.join(self.opts['pki_dir'], self.acc, fn_)):
                    minions.append(fn_)
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
            mlist = []
            for fn_ in salt.utils.isorted(os.listdir(os.path.join(self.opts['pki_dir'], self.acc))):
                if not fn_.startswith('.') and os.path.isfile(os.path.join(self.opts['pki_dir'], self.acc, fn_)):
                    mlist.append(fn_)
            minions = set(mlist)
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
                                                delimiter=delimiter,
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
            mlist = []
            for fn_ in salt.utils.isorted(os.listdir(os.path.join(self.opts['pki_dir'], self.acc))):
                if not fn_.startswith('.') and os.path.isfile(os.path.join(self.opts['pki_dir'], self.acc, fn_)):
                    mlist.append(fn_)
            minions = set(mlist)
        elif cache_enabled:
            minions = os.listdir(os.path.join(self.opts['cachedir'], 'minions'))
        else:
            return []

        if cache_enabled:
            cdir = os.path.join(self.opts['cachedir'], 'minions')
            if not os.path.isdir(cdir):
                return list(minions)

            tgt = expr
            try:
                # Target is an address?
                tgt = ipaddress.ip_address(tgt)
            except:  # pylint: disable=bare-except
                try:
                    # Target is a network?
                    tgt = ipaddress.ip_network(tgt)
                except:  # pylint: disable=bare-except
                    log.error('Invalid IP/CIDR target: {0}'.format(tgt))
                    return []
            proto = 'ipv{0}'.format(tgt.version)

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

                if proto not in grains:
                    match = False
                elif isinstance(tgt, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
                    match = str(tgt) in grains[proto]
                else:
                    match = salt.utils.network.in_subnet(tgt, grains[proto])

                if not match and id_ in minions:
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
                mlist = []
                for fn_ in salt.utils.isorted(os.listdir(os.path.join(self.opts['pki_dir'], self.acc))):
                    if not fn_.startswith('.') and os.path.isfile(os.path.join(self.opts['pki_dir'], self.acc, fn_)):
                        mlist.append(fn_)
                return mlist
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
        log.debug('_check_compound_minions({0}, {1}, {2}, {3})'.format(expr, delimiter, greedy, pillar_exact))
        if not isinstance(expr, six.string_types) and not isinstance(expr, (list, tuple)):
            log.error('Compound target that is neither string, list nor tuple')
            return []
        mlist = []
        for fn_ in salt.utils.isorted(os.listdir(os.path.join(self.opts['pki_dir'], self.acc))):
            if not fn_.startswith('.') and os.path.isfile(os.path.join(self.opts['pki_dir'], self.acc, fn_)):
                mlist.append(fn_)
        minions = set(mlist)
        log.debug('minions: {0}'.format(minions))

        if self.opts.get('minion_data_cache', False):
            ref = {'G': self._check_grain_minions,
                   'P': self._check_grain_pcre_minions,
                   'I': self._check_pillar_minions,
                   'J': self._check_pillar_pcre_minions,
                   'L': self._check_list_minions,
                   'N': None,    # nodegroups should already be expanded
                   'S': self._check_ipcidr_minions,
                   'E': self._check_pcre_minions,
                   'R': self._all_minions}
            if pillar_exact:
                ref['I'] = self._check_pillar_exact_minions
                ref['J'] = self._check_pillar_exact_minions

            results = []
            unmatched = []
            opers = ['and', 'or', 'not', '(', ')']

            if isinstance(expr, six.string_types):
                words = expr.split()
            else:
                words = expr

            for word in words:
                target_info = parse_target(word)

                # Easy check first
                if word in opers:
                    if results:
                        if results[-1] == '(' and word in ('and', 'or'):
                            log.error('Invalid beginning operator after "(": {0}'.format(word))
                            return []
                        if word == 'not':
                            if not results[-1] in ('&', '|', '('):
                                results.append('&')
                            results.append('(')
                            results.append(str(set(minions)))
                            results.append('-')
                            unmatched.append('-')
                        elif word == 'and':
                            results.append('&')
                        elif word == 'or':
                            results.append('|')
                        elif word == '(':
                            results.append(word)
                            unmatched.append(word)
                        elif word == ')':
                            if not unmatched or unmatched[-1] != '(':
                                log.error('Invalid compound expr (unexpected '
                                          'right parenthesis): {0}'
                                          .format(expr))
                                return []
                            results.append(word)
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
                        if word == 'not':
                            results.append('(')
                            results.append(str(set(minions)))
                            results.append('-')
                            unmatched.append('-')
                        elif word == '(':
                            results.append(word)
                            unmatched.append(word)
                        else:
                            log.error(
                                'Expression may begin with'
                                ' binary operator: {0}'.format(word)
                            )
                            return []

                elif target_info and target_info['engine']:
                    if 'N' == target_info['engine']:
                        # Nodegroups should already be expanded/resolved to other engines
                        log.error('Detected nodegroup expansion failure of "{0}"'.format(word))
                        return []
                    engine = ref.get(target_info['engine'])
                    if not engine:
                        # If an unknown engine is called at any time, fail out
                        log.error(
                            'Unrecognized target engine "{0}" for'
                            ' target expression "{1}"'.format(
                                target_info['engine'],
                                word,
                            )
                        )
                        return []

                    engine_args = [target_info['pattern']]
                    if target_info['engine'] in ('G', 'P', 'I', 'J'):
                        engine_args.append(target_info['delimiter'] or ':')
                    engine_args.append(True)

                    results.append(str(set(engine(*engine_args))))
                    if unmatched and unmatched[-1] == '-':
                        results.append(')')
                        unmatched.pop()

                else:
                    # The match is not explicitly defined, evaluate as a glob
                    results.append(str(set(self._check_glob_minions(word, True))))
                    if unmatched and unmatched[-1] == '-':
                        results.append(')')
                        unmatched.pop()

            # Add a closing ')' for each item left in unmatched
            results.extend([')' for item in unmatched])

            results = ' '.join(results)
            log.debug('Evaluating final compound matching expr: {0}'
                      .format(results))
            try:
                return list(eval(results))  # pylint: disable=W0123
            except Exception:
                log.error('Invalid compound target: {0}'.format(expr))
                return []

        return list(minions)

    def connected_ids(self, subset=None, show_ipv4=False, include_localhost=False):
        '''
        Return a set of all connected minion ids, optionally within a subset
        '''
        minions = set()
        if self.opts.get('minion_data_cache', False):
            cdir = os.path.join(self.opts['cachedir'], 'minions')
            if not os.path.isdir(cdir):
                return minions
            addrs = salt.utils.network.local_port_tcp(int(self.opts['publish_port']))
            if '127.0.0.1' in addrs or '0.0.0.0' in addrs:
                # Add in possible ip addresses of a locally connected minion
                addrs.discard('127.0.0.1')
                addrs.discard('0.0.0.0')
                addrs.update(set(salt.utils.network.ip_addrs()))
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
                    if ipv4 == '127.0.0.1' and not include_localhost:
                        continue
                    if ipv4 == '0.0.0.0':
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
        mlist = []
        for fn_ in salt.utils.isorted(os.listdir(os.path.join(self.opts['pki_dir'], self.acc))):
            if not fn_.startswith('.') and os.path.isfile(os.path.join(self.opts['pki_dir'], self.acc, fn_)):
                mlist.append(fn_)
        return mlist

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
               'N': 'node',
               None: 'glob'}

        target_info = parse_target(valid)
        if not target_info:
            log.error('Failed to parse valid target "{0}"'.format(valid))

        v_matcher = ref.get(target_info['engine'])
        v_expr = target_info['pattern']

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
        return vals and all(vals)

    def any_auth(self, form, auth_list, fun, arg, tgt=None, tgt_type='glob'):
        '''
        Read in the form and determine which auth check routine to execute
        '''
        if form == 'publish':
            return self.auth_check(
                    auth_list,
                    fun,
                    arg,
                    tgt,
                    tgt_type)
        return self.spec_check(
                auth_list,
                fun,
                form)

    def auth_check(self,
                   auth_list,
                   funs,
                   args,
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
            args = [args]
        try:
            for num, fun in enumerate(funs):
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
                        if self.validate_tgt(
                                valid,
                                tgt,
                                tgt_type):
                            # Minions are allowed, verify function in allowed list
                            if isinstance(ind[valid], six.string_types):
                                if self.match_check(ind[valid], fun):
                                    return True
                            elif isinstance(ind[valid], list):
                                for cond in ind[valid]:
                                    # Function name match
                                    if isinstance(cond, six.string_types):
                                        if self.match_check(cond, fun):
                                            return True
                                    # Function and args match
                                    elif isinstance(cond, dict):
                                        if len(cond) != 1:
                                            # Invalid argument
                                            continue
                                        fcond = next(six.iterkeys(cond))
                                        # cond: {
                                        #   'mod.func': {
                                        #       'args': [
                                        #           'one.*', 'two\\|three'],
                                        #       'kwargs': {
                                        #           'functioin': 'teach\\|feed',
                                        #           'user': 'mother\\|father'
                                        #           }
                                        #       }
                                        #   }
                                        if self.match_check(fcond, fun):  # check key that is function name match
                                            acond = cond[fcond]
                                            if not isinstance(acond, dict):
                                                # Invalid argument
                                                continue
                                            # whitelist args, kwargs
                                            arg_list = args[num]
                                            cond_args = acond.get('args', [])
                                            good = True
                                            for i, cond_arg in enumerate(cond_args):
                                                if len(arg_list) <= i:
                                                    good = False
                                                    break
                                                if cond_arg is None:  # None == '.*' i.e. allow any
                                                    continue
                                                if not self.match_check(cond_arg, arg_list[i]):
                                                    good = False
                                                    break
                                            if not good:
                                                continue
                                            # Check kwargs
                                            cond_kwargs = acond.get('kwargs', {})
                                            arg_kwargs = {}
                                            for a in arg_list:
                                                if isinstance(a, dict) and '__kwarg__' in a:
                                                    arg_kwargs = a
                                                    break
                                            for k, v in six.iteritems(cond_kwargs):
                                                if k not in arg_kwargs:
                                                    good = False
                                                    break
                                                if v is None:  # None == '.*' i.e. allow any
                                                    continue
                                                if not self.match_check(v, arg_kwargs[k]):
                                                    good = False
                                                    break
                                            if good:
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

    def fill_auth_list_from_ou(self, auth_list, opts=None):
        '''
        Query LDAP, retrieve list of minion_ids from an OU or other search.
        For each minion_id returned from the LDAP search, copy the perms
        matchers into the auth dictionary
        :param auth_list:
        :param opts: __opts__ for when __opts__ is not injected
        :return: Modified auth list.
        '''
        ou_names = []
        for item in auth_list:
            if isinstance(item, six.string_types):
                continue
            ou_names.append([potential_ou for potential_ou in item.keys() if potential_ou.startswith('ldap(')])
        if ou_names:
            auth_list = salt.auth.ldap.expand_ldap_entries(auth_list, opts)
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
            if isinstance(ind, six.string_types):
                if ind.startswith('@') and ind[1:] == mod:
                    return True
                if ind == '@wheel':
                    return True
                if ind == '@wheels':
                    return True
            elif isinstance(ind, dict):
                if len(ind) != 1:
                    continue
                valid = next(six.iterkeys(ind))
                if valid.startswith('@') and valid[1:] == mod:
                    if isinstance(ind[valid], six.string_types):
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
            if isinstance(ind, six.string_types):
                if ind.startswith('@') and ind[1:] == mod:
                    return True
                if ind == '@runners':
                    return True
                if ind == '@runner':
                    return True
            elif isinstance(ind, dict):
                if len(ind) != 1:
                    continue
                valid = next(six.iterkeys(ind))
                if valid.startswith('@') and valid[1:] == mod:
                    if isinstance(ind[valid], six.string_types):
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
            if isinstance(ind, six.string_types):
                if ind.startswith('@') and ind[1:] == mod:
                    return True
                if ind == '@{0}'.format(form):
                    return True
                if ind == '@{0}s'.format(form):
                    return True
            elif isinstance(ind, dict):
                if len(ind) != 1:
                    continue
                valid = next(six.iterkeys(ind))
                if valid.startswith('@') and valid[1:] == mod:
                    if isinstance(ind[valid], six.string_types):
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
