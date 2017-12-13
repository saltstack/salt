# -*- coding: utf-8 -*-
'''
This module contains routines used to verify the matcher against the minions
expected to return
'''

# Import python libs
from __future__ import absolute_import
import logging
import re
import os
import functools

# Import salt libs
import salt.auth.ldap
import salt.cache
import salt.loader
import salt.payload
import salt.utils.args
import salt.utils.data
import salt.utils.files
import salt.utils.network
import salt.utils.stringutils
import salt.utils.versions
from salt.defaults import DEFAULT_TARGET_DELIM
from salt.exceptions import SaltCacheError
from salt.ext import six


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
    grains = None
    pillar = None
    if opts.get('minion_data_cache', False):
        cache = salt.cache.factory(opts)
        if minion is None:
            for id_ in cache.list('minions'):
                data = cache.fetch('minions/{0}'.format(id_), 'data')
                if data is None:
                    continue
        else:
            data = cache.fetch('minions/{0}'.format(minion), 'data')
        if data is not None:
            grains = data.get('grains', None)
            pillar = data.get('pillar', None)
    return minion if minion else None, grains, pillar


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
        log.error('Nodegroup \'%s\' (%s) is neither a string, list nor tuple',
                  nodegroup, nglookup)
        return ''

    skip.add(nodegroup)
    ret = []
    opers = ['and', 'or', 'not', '(', ')']
    for word in words:
        if not isinstance(word, six.string_types):
            word = str(word)
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
        opers_set = set(opers)
        ret = words
        if (set(ret) - opers_set) == set(ret):
            # No compound operators found in nodegroup definition. Check for
            # group type specifiers
            group_type_re = re.compile('^[A-Z]@')
            if not [x for x in ret if '*' in x or group_type_re.match(x)]:
                # No group type specifiers and no wildcards. Treat this as a
                # list of nodenames.
                joined = 'L@' + ','.join(ret)
                log.debug(
                    'Nodegroup \'%s\' (%s) detected as list of nodenames. '
                    'Assuming compound matching syntax of \'%s\'',
                    nodegroup, ret, joined
                )
                # Return data must be a list of compound matching components
                # to be fed into compound matcher. Enclose return data in list.
                return [joined]

        log.debug(
            'No nested nodegroups detected. Using original nodegroup '
            'definition: %s', nodegroups[nodegroup]
        )
        return ret


'''
Used to check what minions should respond from a target

Note: This is a best-effort set of the minions that would match a target.
Depending on master configuration (grains caching, etc.) and topology (syndics)
the list may be a subset-- but we err on the side of too-many minions in this
class.
'''

def pki_dir_acc_path(opts):
    # TODO: this is actually an *auth* check
    if opts.get('transport', 'zeromq') in ('zeromq', 'tcp'):
        return 'minions'
    else:
        return 'accepted'


def pki_dir_minions(opts):
    acc = pki_dir_acc_path(opts)
    minions = []
    for fn_ in salt.utils.data.sorted_ignorecase(os.listdir(os.path.join(opts['pki_dir'], acc))):
        if not fn_.startswith('.') and os.path.isfile(os.path.join(opts['pki_dir'], acc, fn_)):
            minions.append(fn_)
    return minions


def pki_minions(opts):
    '''
    Retreive complete minion list from PKI dir.
    Respects cache if configured
    '''
    acc = pki_dir_acc_path(opts)
    serial = salt.payload.Serial(opts)
    minions = []
    pki_cache_fn = os.path.join(opts['pki_dir'], acc, '.key_cache')
    try:
        if opts['key_cache'] and os.path.exists(pki_cache_fn):
            log.debug('Returning cached minion list')
            with salt.utils.files.fopen(pki_cache_fn) as fn_:
                return serial.load(fn_)
        else:
            minions = pki_dir_minions(opts)
        return minions
    except OSError as exc:
        log.error('Encountered OSError while evaluating  minions in PKI dir: {0}'.format(exc))
        return minions


def check_cache_minions(expr,
                        delimiter,
                        greedy,
                        search_type,
                        opts,
                        regex_match=False,
                        exact_match=False):
    '''
    Helper function to search for minions in master caches
    If 'greedy' return accepted minions that matched by the condition or absend in the cache.
    If not 'greedy' return the only minions have cache data and matched by the condition.
    '''
    cache = salt.cache.factory(opts)
    cache_enabled = opts.get('minion_data_cache', False)

    def list_cached_minions():
        return cache.list('minions')

    if greedy:
        minions = pki_dir_minions(opts)
    elif cache_enabled:
        minions = list_cached_minions()
    else:
        return {'minions': [],
                'missing': []}

    if cache_enabled:
        if greedy:
            cminions = list_cached_minions()
        else:
            cminions = minions
        if not cminions:
            return {'minions': minions,
                    'missing': []}
        minions = set(minions)
        for id_ in cminions:
            if greedy and id_ not in minions:
                continue
            mdata = cache.fetch('minions/{0}'.format(id_), 'data')
            if mdata is None:
                if not greedy:
                    minions.remove(id_)
                continue
            search_results = mdata.get(search_type)
            if not salt.utils.data.subdict_match(search_results,
                                                 expr,
                                                 delimiter=delimiter,
                                                 regex_match=regex_match,
                                                 exact_match=exact_match):
                minions.remove(id_)
        minions = list(minions)
    return {'minions': minions,
            'missing': []}


def check_compound_minions(opts,
                           expr,
                           delimiter,
                           greedy,
                           pillar_exact=False):  # pylint: disable=unused-argument
    '''
    Return the minions found by looking via compound matcher
    '''
    tgts = salt.loader.tgt(opts)
    if not isinstance(expr, six.string_types) and not isinstance(expr, (list, tuple)):
        log.error('Compound target that is neither string, list nor tuple')
        return {'minions': [], 'missing': []}
    minions = set(pki_minions(opts))
    log.debug('minions: {0}'.format(minions))

    def all_minions():
        '''
        Return a list of all minions that have auth'd
        '''
        mlist = pki_dir_minions(opts)
        return {'minions': mlist, 'missing': []}

    if opts.get('minion_data_cache', False):
        ref = {'G': tgts.grain.check_minions,
               'P': tgts.grain_pcre.check_minions,
               'I': tgts.pillar.check_minions,
               'J': tgts.pillar_pcre.check_minions,
               'L': tgts.list.check_minions,
               'N': None,    # nodegroups should already be expanded
               'S': tgts.ipcidr.check_minions,
               'E': tgts.pcre.check_minions,
               'R': all_minions}
        if pillar_exact:
            ref['I'] = tgts.pillar_exact.check_minions
            ref['J'] = tgts.pillar_exact.check_minions

        results = []
        unmatched = []
        opers = ['and', 'or', 'not', '(', ')']
        missing = []

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
                        return {'minions': [], 'missing': []}
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
                            return {'minions': [], 'missing': []}
                        results.append(word)
                        unmatched.pop()
                        if unmatched and unmatched[-1] == '-':
                            results.append(')')
                            unmatched.pop()
                    else:  # Won't get here, unless oper is added
                        log.error('Unhandled oper in compound expr: {0}'
                                  .format(expr))
                        return {'minions': [], 'missing': []}
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
                        return {'minions': [], 'missing': []}

            elif target_info and target_info['engine']:
                if target_info['engine'] == 'N':
                    # Nodegroups should already be expanded/resolved to other engines
                    log.error('Detected nodegroup expansion failure of "{0}"'.format(word))
                    return {'minions': [], 'missing': []}
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
                    return {'minions': [], 'missing': []}

                engine_args = [target_info['pattern']]
                if target_info['engine'] in ('G', 'P', 'I', 'J'):
                    engine_args.append(target_info['delimiter'] or delimiter)
                engine_args.append(greedy)

                _results = engine(*engine_args)
                results.append(str(set(_results['minions'])))
                missing.extend(_results['missing'])
                if unmatched and unmatched[-1] == '-':
                    results.append(')')
                    unmatched.pop()

            else:
                # The match is not explicitly defined, evaluate as a glob
                _results = tgts.glob.check_minions(word, True)
                results.append(str(set(_results['minions'])))
                if unmatched and unmatched[-1] == '-':
                    results.append(')')
                    unmatched.pop()

        # Add a closing ')' for each item left in unmatched
        results.extend([')' for item in unmatched])

        results = ' '.join(results)
        log.debug('Evaluating final compound matching expr: {0}'
                  .format(results))
        try:
            minions = list(eval(results))  # pylint: disable=W0123
            return {'minions': minions, 'missing': missing}
        except Exception:
            log.error('Invalid compound target: {0}'.format(expr))
            return {'minions': [], 'missing': []}

    return {'minions': list(minions),
            'missing': []}

def connected_ids(opts, subset=None, show_ipv4=False, include_localhost=False):
    '''
    Return a set of all connected minion ids, optionally within a subset
    '''
    minions = set()
    cache = salt.cache.factory(opts)
    if opts.get('minion_data_cache', False):
        search = cache.list('minions')
        if search is None:
            return minions
        addrs = salt.utils.network.local_port_tcp(int(opts['publish_port']))
        if '127.0.0.1' in addrs:
            # Add in the address of a possible locally-connected minion.
            addrs.discard('127.0.0.1')
            addrs.update(set(salt.utils.network.ip_addrs(include_loopback=include_localhost)))
        if subset:
            search = subset
        for id_ in search:
            try:
                mdata = cache.fetch('minions/{0}'.format(id_), 'data')
            except SaltCacheError:
                # If a SaltCacheError is explicitly raised during the fetch operation,
                # permission was denied to open the cached data.p file. Continue on as
                # in the releases <= 2016.3. (An explicit error raise was added in PR
                # #35388. See issue #36867 for more information.
                continue
            if mdata is None:
                continue
            grains = mdata.get('grains', {})
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

def check_minions(opts,
                  expr,
                  tgt_type='glob',
                  delimiter=DEFAULT_TARGET_DELIM,
                  greedy=True):
    '''
    Check the passed regex against the available minions' public keys
    stored for authentication. This should return a set of ids which
    match the regex, this will then be used to parse the returns to
    Make sure everyone has checked back in.
    '''
    tgts = salt.loader.tgt(opts)
    if expr is None:
        expr = ''
    fstr = '{0}.check_minions'.format(tgt_type)
    if fstr not in tgts:
        log.warn('Failed to find function for matching minion '
                 'with given tgt_type : {0}, fstr: {1}'
                 .format(tgt_type, fstr))
        return {'minions': [], 'missing': []}

    try:
        fcall = salt.utils.args.format_call(tgts[fstr],
                                            {'expr': expr, 'delimiter': delimiter, 'greedy': greedy},
                                            expected_extra_kws=['delimiter', 'greedy'])
        return tgts[fstr](*fcall['args'], **fcall.get('kwargs', {}))
    except Exception as e:
        log.debug('Targeting module threw {0}'.format(e))
        log.exception(
            'Failed matching available minions with {0} pattern: {1}'
            .format(tgt_type, expr))
        _res = {'minions': [], 'missing': []}
        return _res


def _expand_matching(opts, auth_entry):
    ref = {'G': 'grain',
           'P': 'grain_pcre',
           'I': 'pillar',
           'J': 'pillar_pcre',
           'L': 'list',
           'S': 'ipcidr',
           'E': 'pcre',
           'N': 'node',
           None: 'glob'}

    target_info = parse_target(auth_entry)
    if not target_info:
        log.error('Failed to parse valid target "{0}"'.format(auth_entry))

    v_matcher = ref.get(target_info['engine'])
    v_expr = target_info['pattern']

    _res = check_minions(opts, v_expr, v_matcher)
    return set(_res['minions'])

def validate_tgt(opts, valid, expr, tgt_type, minions=None, expr_form=None):
    '''
    Return a Bool. This function returns if the expression sent in is
    within the scope of the valid expression
    '''
    # remember to remove the expr_form argument from this function when
    # performing the cleanup on this deprecation.
    if expr_form is not None:
        salt.utils.versions.warn_until(
            'Fluorine',
            'the target type should be passed using the \'tgt_type\' '
            'argument instead of \'expr_form\'. Support for using '
            '\'expr_form\' will be removed in Salt Fluorine.'
        )
        tgt_type = expr_form

    v_minions = _expand_matching(opts, valid)
    if minions is None:
        _res = check_minions(opts, expr, tgt_type)
        minions = set(_res['minions'])
    else:
        minions = set(minions)
    d_bool = not bool(minions.difference(v_minions))
    if len(v_minions) == len(minions) and d_bool:
        return True
    return d_bool

def _match_check(regex, fun):
    '''
    Validate a single regex to function comparison, the function argument
    can be a list of functions. It is all or nothing for a list of
    functions
    '''
    vals = []
    if isinstance(fun, six.string_types):
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

def any_auth(opts, form, auth_list, fun, arg, tgt=None, tgt_type='glob'):
    '''
    Read in the form and determine which auth check routine to execute
    '''
    # This function is only called from salt.auth.Authorize(), which is also
    # deprecated and will be removed in Neon.
    salt.utils.versions.warn_until(
        'Neon',
        'The \'any_auth\' function has been deprecated. Support for this '
        'function will be removed in Salt {version}.'
    )
    if form == 'publish':
        return auth_check(opts,
                          auth_list,
                          fun,
                          arg,
                          tgt,
                          tgt_type)
    return spec_check(auth_list,
                      fun,
                      arg,
                      form)

def auth_check_expanded(opts,
                        auth_list,
                        funs,
                        args,
                        tgt,
                        tgt_type='glob',
                        groups=None,
                        publish_validate=False):

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
    if tgt_type.lower() in ('pillar', 'pillar_pcre'):
        v_tgt_type = 'pillar_exact'
    elif tgt_type.lower() == 'compound':
        v_tgt_type = 'compound_pillar_exact'
    _res = check_minions(opts, tgt, v_tgt_type)
    v_minions = set(_res['minions'])

    _res = check_minions(opts, tgt, tgt_type)
    minions = set(_res['minions'])

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
                if _match_check(auth_list_entry, fun):
                    return True
            continue
        if isinstance(auth_list_entry, dict):
            if len(auth_list_entry) != 1:
                log.info('Malformed ACL: {0}'.format(auth_list_entry))
                continue
        allowed_minions.update(set(auth_list_entry.keys()))
        for key in auth_list_entry:
            for match in _expand_matching(opts, key):
                if match in auth_dictionary:
                    auth_dictionary[match].extend(auth_list_entry[key])
                else:
                    auth_dictionary[match] = auth_list_entry[key]

    allowed_minions_from_auth_list = set()
    for next_entry in allowed_minions:
        allowed_minions_from_auth_list.update(_expand_matching(opts, next_entry))
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
                results.append(_match_check(fun, funs))
            if not any(results):
                return False
        return True

    except TypeError:
        return False
    return False

def auth_check(opts,
               auth_list,
               funs,
               args,
               tgt,
               tgt_type='glob',
               groups=None,
               publish_validate=False,
               minions=None,
               whitelist=None):
    '''
    Returns a bool which defines if the requested function is authorized.
    Used to evaluate the standard structure under external master
    authentication interfaces, like eauth, peer, peer_run, etc.
    '''
    if opts.get('auth.enable_expanded_auth_matching', False):
        return auth_check_expanded(opts, auth_list, funs, args, tgt, tgt_type, groups, publish_validate)
    if publish_validate:
        v_tgt_type = tgt_type
        if tgt_type.lower() in ('pillar', 'pillar_pcre'):
            v_tgt_type = 'pillar_exact'
        elif tgt_type.lower() == 'compound':
            v_tgt_type = 'compound_pillar_exact'
        _res = check_minions(opts, tgt, v_tgt_type)
        v_minions = set(_res['minions'])

        _res = check_minions(opts, tgt, tgt_type)
        minions = set(_res['minions'])

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
                    if _match_check(ind, fun):
                        return True
                elif isinstance(ind, dict):
                    if len(ind) != 1:
                        # Invalid argument
                        continue
                    valid = next(six.iterkeys(ind))
                    # Check if minions are allowed
                    if validate_tgt(opts,
                                    valid,
                                    tgt,
                                    tgt_type,
                                    minions=minions):
                        # Minions are allowed, verify function in allowed list
                        fun_args = args[num]
                        fun_kwargs = fun_args[-1] if fun_args else None
                        if isinstance(fun_kwargs, dict) and '__kwarg__' in fun_kwargs:
                            fun_args = list(fun_args)  # copy on modify
                            del fun_args[-1]
                        else:
                            fun_kwargs = None
                        if _fun_check(ind[valid], fun, fun_args, fun_kwargs):
                            return True
    except TypeError:
        return False
    return False

def fill_auth_list_from_groups(auth_provider, user_groups, auth_list):
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

def fill_auth_list(opts, auth_provider, name, groups, auth_list=None, permissive=None):
    '''
    Returns a list of authorisation matchers that a user is eligible for.
    This list is a combination of the provided personal matchers plus the
    matchers of any group the user is in.
    '''
    if auth_list is None:
        auth_list = []
    if permissive is None:
        permissive = opts.get('permissive_acl')
    name_matched = False
    for match in auth_provider:
        if match == '*' and not permissive:
            continue
        if match.endswith('%'):
            if match.rstrip('%') in groups:
                auth_list.extend(auth_provider[match])
        else:
            if salt.utils.stringutils.expr_match(match, name):
                name_matched = True
                auth_list.extend(auth_provider[match])
    if not permissive and not name_matched and '*' in auth_provider:
        auth_list.extend(auth_provider['*'])
    return auth_list

def wheel_check(auth_list, fun, args):
    '''
    Check special API permissions
    '''
    return spec_check(auth_list, fun, args, 'wheel')

def runner_check(auth_list, fun, args):
    '''
    Check special API permissions
    '''
    return spec_check(auth_list, fun, args, 'runner')

def spec_check(auth_list, fun, args, form):
    '''
    Check special API permissions
    '''
    if not auth_list:
        return False
    if form != 'cloud':
        comps = fun.split('.')
        if len(comps) != 2:
            # Hint at a syntax error when command is passed improperly,
            # rather than returning an authentication error of some kind.
            # See Issue #21969 for more information.
            return {'error': {'name': 'SaltInvocationError',
                              'message': 'A command invocation error occurred: Check syntax.'}}
        mod_name = comps[0]
        fun_name = comps[1]
    else:
        fun_name = mod_name = fun
    for ind in auth_list:
        if isinstance(ind, six.string_types):
            if ind[0] == '@':
                if ind[1:] == mod_name or ind[1:] == form or ind == '@{0}s'.format(form):
                    return True
        elif isinstance(ind, dict):
            if len(ind) != 1:
                continue
            valid = next(six.iterkeys(ind))
            if valid[0] == '@':
                if valid[1:] == mod_name:
                    if _fun_check(ind[valid], fun_name, args.get('arg'), args.get('kwarg')):
                        return True
                if valid[1:] == form or valid == '@{0}s'.format(form):
                    if _fun_check(ind[valid], fun, args.get('arg'), args.get('kwarg')):
                        return True
    return False

def _fun_check(valid, fun, args=None, kwargs=None):
    '''
    Check the given function name (fun) and its arguments (args) against the list of conditions.
    '''
    if not isinstance(valid, list):
        valid = [valid]
    for cond in valid:
        # Function name match
        if isinstance(cond, six.string_types):
            if _match_check(cond, fun):
                return True
        # Function and args match
        elif isinstance(cond, dict):
            if len(cond) != 1:
                # Invalid argument
                continue
            fname_cond = next(six.iterkeys(cond))
            if _match_check(fname_cond, fun):  # check key that is function name match
                if _args_check(cond[fname_cond], args, kwargs):
                    return True
    return False

def _args_check(valid, args=None, kwargs=None):
    '''
    valid is a dicts: {'args': [...], 'kwargs': {...}} or a list of such dicts.
    '''
    if not isinstance(valid, list):
        valid = [valid]
    for cond in valid:
        if not isinstance(cond, dict):
            # Invalid argument
            continue
        # whitelist args, kwargs
        cond_args = cond.get('args', [])
        good = True
        for i, cond_arg in enumerate(cond_args):
            if args is None or len(args) <= i:
                good = False
                break
            if cond_arg is None:  # None == '.*' i.e. allow any
                continue
            if not _match_check(cond_arg, str(args[i])):
                good = False
                break
        if not good:
            continue
        # Check kwargs
        cond_kwargs = cond.get('kwargs', {})
        for k, v in six.iteritems(cond_kwargs):
            if kwargs is None or k not in kwargs:
                good = False
                break
            if v is None:  # None == '.*' i.e. allow any
                continue
            if not _match_check(v, str(kwargs[k])):
                good = False
                break
        if good:
            return True
    return False


def mine_get(tgt, fun, tgt_type='glob', opts=None):
    '''
    Gathers the data from the specified minions' mine, pass in the target,
    function to look up and the target type
    '''
    ret = {}
    _res = check_minions(opts, tgt, tgt_type)
    minions = _res['minions']
    cache = salt.cache.factory(opts)
    for minion in minions:
        mdata = cache.fetch('minions/{0}'.format(minion), 'mine')
        if mdata is None:
            continue
        fdata = mdata.get(fun)
        if fdata:
            ret[minion] = fdata
    return ret
