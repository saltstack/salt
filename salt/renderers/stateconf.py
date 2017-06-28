# -*- coding: utf-8 -*-
'''
A flexible renderer that takes a templating engine and a data format

:maintainer: Jack Kuan <kjkuan@gmail.com>
:maturity: new
:platform: all
'''
# See http://docs.saltstack.org/en/latest/ref/renderers/all/salt.renderers.stateconf.html
# for a guide to using this module.
#
# FIXME: I really need to review and simplify this renderer, it's getting out of hand!
#
# TODO:
#   - sls meta/info state: E.g.,
#
#       sls_info:
#         stateconf.set:
#           - author: Jack Kuan
#           - description: what the salt file does...
#           - version: 0.1.0
#
#   - version constraint for 'include'. E.g.,
#
#       include:
#         - apache: >= 0.1.0
#

# Import python libs
from __future__ import absolute_import
import logging
import re
import getopt
import copy
from os import path as ospath

# Import salt libs
import salt.utils
from salt.exceptions import SaltRenderError

# Import 3rd-party libs
import salt.ext.six as six
from salt.ext.six.moves import StringIO  # pylint: disable=import-error

__all__ = ['render']

log = logging.getLogger(__name__)


__opts__ = {
    'stateconf_end_marker': r'#\s*-+\s*end of state config\s*-+',
    # e.g., something like "# --- end of state config --" works by default.

    'stateconf_start_state': '.start',
    # name of the state id for the generated start state.

    'stateconf_goal_state': '.goal',
    # name of the state id for the generated goal state.

    'stateconf_state_func': 'stateconf.set'
    # names the state and the state function to be recognized as a special
    # state from which to gather sls file context variables. It should be
    # specified in the 'state.func' notation, and both the state module and
    # the function must actually exist and the function should be a dummy,
    # no-op state function that simply returns a
    # dict(name=name, result=True, changes={}, comment='')
}

STATE_FUNC = STATE_NAME = ''


def __init__(opts):
    global STATE_NAME, STATE_FUNC
    STATE_FUNC = __opts__['stateconf_state_func']
    STATE_NAME = STATE_FUNC.split('.')[0]


MOD_BASENAME = ospath.basename(__file__)
INVALID_USAGE_ERROR = SaltRenderError(
    'Invalid use of {0} renderer!\n'
    '''Usage: #!{1} [-GoSp] [<data_renderer> [options] . <template_renderer> [options]]

where an example <data_renderer> would be yaml and a <template_renderer> might
be jinja. Each renderer can be passed its renderer specific options.

Options(for this renderer):

  -G   Do not generate the goal state that requires all other states in the sls.

  -o   Indirectly order the states by adding requires such that they will be
       executed in the order they are defined in the sls. Implies using yaml -o.

  -s   Generate the start state that gets inserted as the first state in
       the sls. This only makes sense if your high state data dict is ordered.

  -p   Assume high state input. This option allows you to pipe high state data
       through this renderer. With this option, the use of stateconf.set state
       in the sls will have no effect, but other features of the renderer still
       apply.

  '''.format(MOD_BASENAME, MOD_BASENAME)
)


def render(input, saltenv='base', sls='', argline='', **kws):
    gen_start_state = False
    no_goal_state = False
    implicit_require = False

    def process_sls_data(data, context=None, extract=False):
        sls_dir = ospath.dirname(sls.replace('.', ospath.sep)) if '.' in sls else sls
        ctx = dict(sls_dir=sls_dir if sls_dir else '.')

        if context:
            ctx.update(context)

        tmplout = render_template(
                StringIO(data), saltenv, sls, context=ctx,
                argline=rt_argline.strip(), **kws
        )
        high = render_data(tmplout, saltenv, sls, argline=rd_argline.strip())
        return process_high_data(high, extract)

    def process_high_data(high, extract):
        # make a copy so that the original, un-preprocessed highstate data
        # structure can be used later for error checking if anything goes
        # wrong during the preprocessing.
        data = copy.deepcopy(high)
        try:
            rewrite_single_shorthand_state_decl(data)
            rewrite_sls_includes_excludes(data, sls, saltenv)

            if not extract and implicit_require:
                sid = has_names_decls(data)
                if sid:
                    raise SaltRenderError(
                        '\'names\' declaration(found in state id: {0}) is '
                        'not supported with implicitly ordered states! You '
                        'should generate the states in a template for-loop '
                        'instead.'.format(sid)
                    )
                add_implicit_requires(data)

            if gen_start_state:
                add_start_state(data, sls)

            if not extract and not no_goal_state:
                add_goal_state(data)

            rename_state_ids(data, sls)

            # We must extract no matter what so extending a stateconf sls file
            # works!
            extract_state_confs(data)
        except SaltRenderError:
            raise
        except Exception as err:
            log.exception(
                'Error found while pre-processing the salt file '
                '{0}:\n{1}'.format(sls, err)
            )
            from salt.state import State
            state = State(__opts__)
            errors = state.verify_high(high)
            if errors:
                raise SaltRenderError('\n'.join(errors))
            raise SaltRenderError('sls preprocessing/rendering failed!')
        return data
    # ----------------------
    renderers = kws['renderers']
    opts, args = getopt.getopt(argline.split(), 'Gosp')
    argline = ' '.join(args) if args else 'yaml . jinja'

    if ('-G', '') in opts:
        no_goal_state = True
    if ('-o', '') in opts:
        implicit_require = True
    if ('-s', '') in opts:
        gen_start_state = True

    if ('-p', '') in opts:
        data = process_high_data(input, extract=False)
    else:
        # Split on the first dot surrounded by spaces but not preceded by a
        # backslash. A backslash preceded dot will be replaced with just dot.
        args = [
            arg.strip().replace('\\.', '.')
            for arg in re.split(r'\s+(?<!\\)\.\s+', argline, 1)
        ]
        try:
            name, rd_argline = (args[0] + ' ').split(' ', 1)
            render_data = renderers[name]  # e.g., the yaml renderer
            if implicit_require:
                if name == 'yaml':
                    rd_argline = '-o ' + rd_argline
                else:
                    raise SaltRenderError(
                        'Implicit ordering is only supported if the yaml renderer '
                        'is used!'
                    )
            name, rt_argline = (args[1] + ' ').split(' ', 1)
            render_template = renderers[name]  # e.g., the mako renderer
        except KeyError as err:
            raise SaltRenderError('Renderer: {0} is not available!'.format(err))
        except IndexError:
            raise INVALID_USAGE_ERROR

        if isinstance(input, six.string_types):
            with salt.utils.fopen(input, 'r') as ifile:
                sls_templ = ifile.read()
        else:  # assume file-like
            sls_templ = input.read()

        # first pass to extract the state configuration
        match = re.search(__opts__['stateconf_end_marker'], sls_templ)
        if match:
            process_sls_data(sls_templ[:match.start()], extract=True)

        # if some config has been extracted then remove the sls-name prefix
        # of the keys in the extracted stateconf.set context to make them easier
        # to use in the salt file.
        if STATE_CONF:
            tmplctx = STATE_CONF.copy()
            if tmplctx:
                prefix = sls + '::'
                for k in six.iterkeys(tmplctx):  # iterate over a copy of keys
                    if k.startswith(prefix):
                        tmplctx[k[len(prefix):]] = tmplctx[k]
                        del tmplctx[k]
        else:
            tmplctx = {}

        # do a second pass that provides the extracted conf as template context
        data = process_sls_data(sls_templ, tmplctx)

    if log.isEnabledFor(logging.DEBUG):
        import pprint  # FIXME: pprint OrderedDict
        log.debug('Rendered sls: {0}'.format(pprint.pformat(data)))
    return data


def has_names_decls(data):
    for sid, _, _, args in statelist(data):
        if sid == 'extend':
            continue
        for _ in nvlist(args, ['names']):
            return sid


def rewrite_single_shorthand_state_decl(data):  # pylint: disable=C0103
    '''
    Rewrite all state declarations that look like this::

      state_id_decl:
        state.func

    into::

      state_id_decl:
        state.func: []
    '''
    for sid, states in six.iteritems(data):
        if isinstance(states, six.string_types):
            data[sid] = {states: []}


def rewrite_sls_includes_excludes(data, sls, saltenv):
    # if the path of the included/excluded sls starts with a leading dot(.)
    # then it's taken to be relative to the including/excluding sls.
    for sid in data:
        if sid == 'include':
            includes = data[sid]
            for i, each in enumerate(includes):
                if isinstance(each, dict):
                    slsenv, incl = each.popitem()
                else:
                    slsenv = saltenv
                    incl = each
                if incl.startswith('.'):
                    includes[i] = {slsenv: _relative_to_abs_sls(incl, sls)}
        elif sid == 'exclude':
            for sdata in data[sid]:
                if 'sls' in sdata and sdata['sls'].startswith('.'):
                    sdata['sls'] = _relative_to_abs_sls(sdata['sls'], sls)


def _local_to_abs_sid(sid, sls):  # id must starts with '.'
    if '::' in sid:
        return _relative_to_abs_sls(sid, sls)
    else:
        abs_sls = _relative_to_abs_sls(sid, sls + '.')
        return '::'.join(abs_sls.rsplit('.', 1))


def _relative_to_abs_sls(relative, sls):
    '''
    Convert ``relative`` sls reference into absolute, relative to ``sls``.
    '''
    levels, suffix = re.match(r'^(\.+)(.*)$', relative).groups()
    level_count = len(levels)
    p_comps = sls.split('.')
    if level_count > len(p_comps):
        raise SaltRenderError(
            'Attempted relative include goes beyond top level package'
        )
    return '.'.join(p_comps[:-level_count] + [suffix])


def nvlist(thelist, names=None):
    '''
    Given a list of items::

        - whatever
        - name1: value1
        - name2:
          - key: value
          - key: value

    return a generator that yields each (item, key, value) tuple, skipping
    items that are not name-value's(dictionaries) or those not in the
    list of matching names. The item in the returned tuple is the single-key
    dictionary.
    '''
    # iterate over the list under the state dict.
    for nvitem in thelist:
        if isinstance(nvitem, dict):
            # then nvitem is a name-value item(a dict) of the list.
            name, value = next(six.iteritems(nvitem))
            if names is None or name in names:
                yield nvitem, name, value


def nvlist2(thelist, names=None):
    '''
    Like nvlist but applied one more time to each returned value.
    So, given a list, args,  of arguments to a state like this::

      - name: echo test
      - cwd: /
      - require:
        - file: test.sh

    nvlist2(args, ['require']) would yield the tuple,
    (dict_item, 'file', 'test.sh') where dict_item is the single-key
    dictionary of {'file': 'test.sh'}.

    '''
    for _, _, value in nvlist(thelist, names):
        for each in nvlist(value):
            yield each


def statelist(states_dict, sid_excludes=frozenset(['include', 'exclude'])):
    for sid, states in six.iteritems(states_dict):
        if sid.startswith('__'):
            continue
        if sid in sid_excludes:
            continue
        for sname, args in six.iteritems(states):
            if sname.startswith('__'):
                continue
            yield sid, states, sname, args


REQUISITES = set([
    'require', 'require_in', 'watch', 'watch_in', 'use', 'use_in', 'listen', 'listen_in'
])


def rename_state_ids(data, sls, is_extend=False):
    # if the .sls file is salt://my/salt/file.sls
    # then rename all state ids defined in it that start with a dot(.) with
    # "my.salt.file::" + the_state_id_without_the_first_dot.

    # update "local" references to the renamed states.

    if 'extend' in data and not is_extend:
        rename_state_ids(data['extend'], sls, True)

    for sid, _, _, args in statelist(data):
        for req, sname, sid in nvlist2(args, REQUISITES):
            if sid.startswith('.'):
                req[sname] = _local_to_abs_sid(sid, sls)

    for sid in list(data):
        if sid.startswith('.'):
            newsid = _local_to_abs_sid(sid, sls)
            if newsid in data:
                raise SaltRenderError(
                    'Can\'t rename state id({0}) into {1} because the later '
                    'already exists!'.format(sid, newsid)
                )
            # add a '- name: sid' to those states without '- name'.
            for sname, args in six.iteritems(data[sid]):
                if state_name(sname) == STATE_NAME:
                    continue
                for arg in args:
                    if isinstance(arg, dict) and next(iter(arg)) == 'name':
                        break
                else:
                    # then no '- name: ...' is defined in the state args
                    # add the sid without the leading dot as the name.
                    args.insert(0, dict(name=sid[1:]))
            data[newsid] = data[sid]
            del data[sid]


REQUIRE = set(['require', 'watch', 'listen'])
REQUIRE_IN = set(['require_in', 'watch_in', 'listen_in'])
EXTENDED_REQUIRE = {}
EXTENDED_REQUIRE_IN = {}

from itertools import chain


# To avoid cycles among states when each state requires the one before it:
#   explicit require/watch/listen can only contain states before it
#   explicit require_in/watch_in/listen_in can only contain states after it
def add_implicit_requires(data):

    def T(sid, state):  # pylint: disable=C0103
        return '{0}:{1}'.format(sid, state_name(state))

    states_before = set()
    states_after = set()

    for sid in data:
        for state in data[sid]:
            states_after.add(T(sid, state))

    prev_state = (None, None)  # (state_name, sid)
    for sid, states, sname, args in statelist(data):
        if sid == 'extend':
            for esid, _, _, eargs in statelist(states):
                for _, rstate, rsid in nvlist2(eargs, REQUIRE):
                    EXTENDED_REQUIRE.setdefault(
                        T(esid, rstate), []).append((None, rstate, rsid))
                for _, rstate, rsid in nvlist2(eargs, REQUIRE_IN):
                    EXTENDED_REQUIRE_IN.setdefault(
                        T(esid, rstate), []).append((None, rstate, rsid))
            continue

        tag = T(sid, sname)
        states_after.remove(tag)

        reqs = nvlist2(args, REQUIRE)
        if tag in EXTENDED_REQUIRE:
            reqs = chain(reqs, EXTENDED_REQUIRE[tag])
        for _, rstate, rsid in reqs:
            if T(rsid, rstate) in states_after:
                raise SaltRenderError(
                    'State({0}) can\'t require/watch/listen a state({1}) defined '
                    'after it!'.format(tag, T(rsid, rstate))
                )

        reqs = nvlist2(args, REQUIRE_IN)
        if tag in EXTENDED_REQUIRE_IN:
            reqs = chain(reqs, EXTENDED_REQUIRE_IN[tag])
        for _, rstate, rsid in reqs:
            if T(rsid, rstate) in states_before:
                raise SaltRenderError(
                    'State({0}) can\'t require_in/watch_in/listen_in a state({1}) '
                    'defined before it!'.format(tag, T(rsid, rstate))
                )

        # add a (- state: sid) item, at the beginning of the require of this
        # state if there's a state before this one.
        if prev_state[0] is not None:
            try:
                next(nvlist(args, ['require']))[2].insert(0, dict([prev_state]))
            except StopIteration:  # i.e., there's no require
                args.append(dict(require=[dict([prev_state])]))

        states_before.add(tag)
        prev_state = (state_name(sname), sid)


def add_start_state(data, sls):
    start_sid = __opts__['stateconf_start_state']
    if start_sid in data:
        raise SaltRenderError(
            'Can\'t generate start state({0})! The same state id already '
            'exists!'.format(start_sid)
        )
    if not data:
        return

    # the start state is either the first state whose id declaration has
    # no __sls__, or it's the first state whose id declaration has a
    # __sls__ == sls.
    non_sids = set(['include', 'exclude', 'extend'])
    for sid, states in six.iteritems(data):
        if sid in non_sids or sid.startswith('__'):
            continue
        if '__sls__' not in states or states['__sls__'] == sls:
            break
    else:
        raise SaltRenderError('Can\'t determine the first state in the sls file!')
    reqin = {state_name(next(six.iterkeys(data[sid]))): sid}
    data[start_sid] = {STATE_FUNC: [{'require_in': [reqin]}]}


def add_goal_state(data):
    goal_sid = __opts__['stateconf_goal_state']
    if goal_sid in data:
        raise SaltRenderError(
            'Can\'t generate goal state({0})! The same state id already '
            'exists!'.format(goal_sid)
        )
    else:
        reqlist = []
        for sid, states, state, _ in \
                statelist(data, set(['include', 'exclude', 'extend'])):
            if '__sls__' in states:
                # Then id declaration must have been included from a
                # rendered sls. Currently, this is only possible with
                # pydsl's high state output.
                continue
            reqlist.append({state_name(state): sid})
        data[goal_sid] = {STATE_FUNC: [dict(require=reqlist)]}


def state_name(sname):
    '''
    Return the name of the state regardless if sname is
    just the state name or a state.func name.
    '''
    return sname.split('.', 1)[0]


# Quick and dirty way to get attribute access for dictionary keys.
# So, we can do: ${apache.port} instead of ${apache['port']} when possible.
class Bunch(dict):
    def __getattr__(self, name):
        return self[name]


# With sls:
#
#   state_id:
#     stateconf.set:
#       - name1: value1
#
# STATE_CONF is:
#    { state_id => {name1: value1} }
#
STATE_CONF = {}       # stateconf.set
STATE_CONF_EXT = {}   # stateconf.set under extend: ...


def extract_state_confs(data, is_extend=False):
    for state_id, state_dict in six.iteritems(data):
        if state_id == 'extend' and not is_extend:
            extract_state_confs(state_dict, True)
            continue

        if STATE_NAME in state_dict:
            key = STATE_NAME
        elif STATE_FUNC in state_dict:
            key = STATE_FUNC
        else:
            continue

        to_dict = STATE_CONF_EXT if is_extend else STATE_CONF
        conf = to_dict.setdefault(state_id, Bunch())
        for sdk in state_dict[key]:
            if not isinstance(sdk, dict):
                continue
            key, val = next(six.iteritems(sdk))
            conf[key] = val

        if not is_extend and state_id in STATE_CONF_EXT:
            extend = STATE_CONF_EXT[state_id]
            for requisite in 'require', 'watch', 'listen':
                if requisite in extend:
                    extend[requisite] += to_dict[state_id].get(requisite, [])
            to_dict[state_id].update(STATE_CONF_EXT[state_id])
