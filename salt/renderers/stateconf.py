'''
This module provides a custom renderer that process a salt file with a
specified templating engine(eg, jinja) and a chosen data renderer(eg, yaml),
extract arguments for any ``stateconf.set`` state and provide the extracted
arguments (including salt specific args, such as 'require', etc) as template
context. The goal is to make writing reusable/configurable/ parameterized
salt files easier and cleaner.

To use this renderer, either set it as the default renderer via the
``renderer`` option in master/minion's config, or use the shebang line in each
individual sls file, like so: ``#!stateconf``. Note, due to the way this
renderer works, it must be specified as the first renderer in a render
pipeline. That is, you cannot specify ``#!mako|yaml|stateconf``, for example.
Instead, you specify them as renderer arguments: ``#!stateconf mako . yaml``.

Here's a list of features enabled by this renderer:

  - Recognizes the special state function, ``stateconf.set``, that configures a
    default list of named arguments useable within the template context of
    the salt file. Example::

        sls_params:
          stateconf.set:
            - name1: value1
            - name2: value2
            - name3:
              - value1
              - value2
              - value3
            - require_in:
              - cmd: output

        # --- end of state config ---

        output:
          cmd.run:
            - name: |
                echo 'name1={{sls_params.name1}}
                      name2={{sls_params.name2}}
                      name3[1]={{sls_params.name3[1]}}
                '

    This even works with ``include`` + ``extend`` so that you can override
    the default configured arguments by including the salt file and then
    ``extend`` the ``stateconf.set`` states that come from the included salt
    file.

    Notice that the end of configuration marker(``# --- end of state config --``)
    is needed to separate the use of 'stateconf.set' form the rest of your salt
    file. The regex that matches such marker can be configured via the
    ``stateconf_end_marker`` option in your master or minion config file.

    Sometimes, you'd like to set a default argument value that's based on
    earlier arguments in the same ``stateconf.set``. For example, you may be
    tempted to do something like this::

        apache:
          stateconf.set:
            - host: localhost
            - port: 1234
            - url: 'http://{{host}}:{{port}}/'

        # --- end of state config ---

        test:
          cmd.run:
            - name: echo '{{apache.url}}'
            - cwd: /

    However, this won't work, but can be worked around like so::

        apache:
          stateconf.set:
            - host: localhost
            - port: 1234
        {#  - url: 'http://{{host}}:{{port}}/' #}

        # --- end of state config ---
        # {{ apache.setdefault('url', "http://%(host)s:%(port)s/" % apache) }}

        test:
          cmd.run:
            - name: echo '{{apache.url}}'
            - cwd: /

  - Adds support for relative include and exclude of .sls files. Example::

        include:
          - .apache
          - .db.mysql

        exclude:
          - sls: .users

    If the above is written in a salt file at `salt://some/where.sls` then
    it will include `salt://some/apache.sls` and `salt://some/db/mysql.sls`,
    and exclude `salt://some/users.ssl`. Actually, it does that by rewriting
    the above ``include`` and ``exclude`` into::

        include:
          - some.apache
          - some.db.mysql

        exclude:
          - sls: some.users


  - Adds a ``sls_dir`` context variable that expands to the directory containing
    the rendering salt file. So, you can write ``salt://${sls_dir}/...`` to
    reference templates files used by your salt file.

  - Prefixes any state id(declaration or reference) that starts with a dot(``.``)
    to avoid duplicated state ids when the salt file is included by other salt
    files.

    For example, in the `salt://some/file.sls`, a state id such as ``.sls_params``
    will be turned into ``some.file::sls_params``. Example::

        .vim:
          package.installed

    Above will be translated into::

        some.file::vim:
          package.installed:
            - name: vim
    
    Notice how that if a state under a dot-prefixed state id has no ``name``
    argument then one will be added automatically by using the state id with
    the leading dot stripped off.

    The leading dot trick can be used with extending state ids as well,
    so you can include relatively and extend relatively. For example, when
    extending a state in `salt://some/other_file.sls`, eg,::

        include:
          - .file

        extend:
          .file::sls_params:
            stateconf.set:
              - name1: something

    Above will be pre-processed into::

        include:
          - some.file

        extend:
          some.file::sls_params:
            stateconf.set:
              - name1: something

  - Optionally(enabled by default, *disable* via the `-G` renderer option,
    eg, in the shebang line: ``#!stateconf -G``), generates a
    ``stateconf.set`` goal state(state id named as ``.goal`` by default,
    configurable via the master/minion config option, ``stateconf_goal_state``)
    that requires all other states in the salt file. Note, the ``.goal``
    state id is subject to dot-prefix rename rule mentioned earlier.

    Such goal state is intended to be required by some state in an including
    salt file. For example, in your webapp salt file, if you include a
    sls file that is supposed to setup Tomcat, you might want to make sure that
    all states in the Tomcat sls file will be executed before some state in
    the webapp sls file.

  - Optionally(enable via the `-o` renderer option, eg, in the shebang line:
    ``#!stateconf -o``), orders the states in a sls file by adding a
    ``require`` requisite to each state such that every state requires the
    state defined just before it. The order of the states here is the order
    they are defined in the sls file.(Note: this feature is only available
    if your minions are using Python >= 2.7. For Python2.6, it should also
    work if you install the `ordereddict` module from PyPI)

    By enabling this feature, you are basically agreeing to author your sls
    files in a way that gives up the explicit(or implicit?) ordering imposed
    by the use of ``require``, ``watch``, ``require_in`` or ``watch_in``
    requisites, and instead, you rely on the order of states you define in
    the sls files. This may or may not be a better way for you. However, if
    there are many states defined in a sls file, then it tends to be easier
    to see the order they will be executed with this feature.

    You are still allowed to use all the requisites, with a few restricitons.
    You cannot ``require`` or ``watch`` a state defined *after* the current
    state. Similarly, in a state, you cannot ``require_in`` or ``watch_in``
    a state defined *before* it. Breaking any of the two restrictions above
    will result in a state loop. The renderer will check for such incorrect
    uses if this feature is enabled.

    Additionally, ``names`` declarations cannot be used with this feature
    because the way they are compiled into low states make it impossible to
    guarantee the order in which they will be executed. This is also checked
    by the renderer. As a workaround for not being able to use ``names``,
    you can achieve the same effect, by generate your states with the
    template engine available within your sls file.

    Finally, with the use of this feature, it becomes possible to easily make
    an included sls file execute all its states *after* some state(say, with
    id ``X``) in the including sls file.  All you have to do is to make state,
    ``X``, ``require_in`` the first state defined in the included sls file.


When writing sls files with this renderer, you should avoid using what can be
defined in a ``name`` argument of a state as the state's id. That is, avoid
writing your states like this::

    /path/to/some/file:
      file.managed:
        - source: salt://some/file

    cp /path/to/some/file file2:
      cmd.run:
        - cwd: /
        - require:
          - file: /path/to/some/file

Instead, you should define the state id and the ``name`` argument separately
for each state, and the id should be something meaningful and easy to reference
within a requisite(which I think is a good habit anyway, and such extra
indirection would also makes your sls file easier to modify later). Thus, the
above states should be written like this::

    add-some-file:
      file.managed:
        - name: /path/to/some/file
        - source: salt://some/file

    copy-files:
      cmd.run:
        - name: cp /path/to/some/file file2
        - cwd: /
        - require:
          - file: add-some-file

Moreover, when referencing a state from a requisite, you should reference the
state's id plus the state name rather than the state name plus its ``name``
argument. (Yes, in the above example, you can actually ``require`` the
``file: /path/to/some/file``, instead of the ``file: add-some-file``). The
reason is that this renderer will re-write or rename state id's and their
references for state id's prefixed with ``.``. So, if you reference ``name``
then there's no way to reliably rewrite such reference.

'''

# TODO:
#   - sls meta/info state: Eg,
#
#       sls_info:
#         stateconf.set:
#           - author: Jack Kuan
#           - description: what the salt file does...
#           - version: 0.1.0
#
#   - version constraint for 'include'. Eg,
#
#       include:
#         - apache: >= 0.1.0
#

# Import python libs
import sys
import logging
import re
import getopt
import copy
from os import path as ospath
from cStringIO import StringIO

# Import salt libs
import salt.utils
from salt.renderers.yaml import HAS_ORDERED_DICT
from salt.exceptions import SaltRenderError

__all__ = [ 'render' ]

log = logging.getLogger(__name__)


__opts__ = {
    'stateconf_end_marker': r'#\s*-+\s*end of state config\s*-+',
    # eg, something like "# --- end of state config --" works by default.

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
    '''Usage: #!{1} [-Go] <data_renderer> [options] . <template_renderer> [options]

where an example <data_renderer> would be yaml and a <template_renderer> might
be jinja. Each renderer can be passed its renderer specific options.

Options(for this renderer):

  -G   Do not generate the goal state that requires all other states in the sls.

  -o   Indirectly order the states by adding requires such that they will be
       executed in the order they are defined in the sls. Implies using yaml -o.
  '''.format(MOD_BASENAME, MOD_BASENAME)
)


def render(template_file, env='', sls='', argline='', **kws):
    NO_GOAL_STATE = False
    IMPLICIT_REQUIRE = False

    renderers = kws['renderers']
    opts, args = getopt.getopt(argline.split(), 'Go')
    argline = ' '.join(args) if args else 'yaml . jinja'

    if ('-G', '') in opts:
        NO_GOAL_STATE = True

    # Split on the first dot surrounded by spaces but not preceded by a
    # backslash. A backslash preceded dot will be replaced with just dot.
    args = [
        arg.strip().replace('\\.', '.')
        for arg in re.split(r'\s+(?<!\\)\.\s+', argline, 1)
    ]
    try:
        name, rd_argline = (args[0] + ' ').split(' ', 1)
        render_data = renderers[name]  # eg, the yaml renderer
        if ('-o', '') in opts:
            if name == 'yaml':
                IMPLICIT_REQUIRE = True
                rd_argline = '-o ' + rd_argline
            else:
                raise SaltRenderError(
                    'Implicit ordering is only supported if the yaml renderer '
                    'is used!'
                )
        name, rt_argline = (args[1] + ' ').split(' ', 1)
        render_template = renderers[name]  # eg, the mako renderer
    except KeyError, e:
        raise SaltRenderError('Renderer: {0} is not available!'.format(e))
    except IndexError, e:
        raise INVALID_USAGE_ERROR

    def process_sls_data(data, context=None, extract=False):
        sls_dir = ospath.dirname(sls.replace('.', ospath.sep))
        ctx = dict(sls_dir=sls_dir if sls_dir else '.')

        if context:
            ctx.update(context)

        tmplout = render_template(
                StringIO(data), env, sls, context=ctx,
                argline=rt_argline.strip(), **kws
        )
        high = render_data(tmplout, env, sls, argline=rd_argline.strip())

        # make a copy so that the original, un-preprocessed highstate data
        # structure can be used later for error checking if anything goes
        # wrong during the preprocessing.
        data = copy.deepcopy(high)
        try:
            rewrite_single_shorthand_state_decl(data)
            rewrite_sls_includes_excludes(data, sls)

            if not extract and IMPLICIT_REQUIRE:
                sid = has_names_decls(data)
                if sid:
                    raise SaltRenderError(
                        '\'names\' declaration(found in state id: {0}) is '
                        'not supported with implicitly ordered states! You '
                        'should generate the states in a template for-loop '
                        'instead.'.format(sid)
                    )
                add_implicit_requires(data)

            if not extract and not NO_GOAL_STATE:
                add_goal_state(data)

            rename_state_ids(data, sls)

            if extract:
                extract_state_confs(data)

        except Exception, e:
            if isinstance(e, SaltRenderError):
                raise
            log.exception(
                'Error found while pre-processing the salt file, '
                '{0}.\n'.format(sls)
            )
            from salt.state import State
            state = State(__opts__)
            errors = state.verify_high(high)
            if errors:
                raise SaltRenderError('\n'.join(errors))
            raise SaltRenderError('sls preprocessing/rendering failed!')
        return data

    if isinstance(template_file, basestring):
        with salt.utils.fopen(template_file, 'r') as f:
            sls_templ = f.read()
    else:  # assume file-like
        sls_templ = template_file.read()

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
            for k in tmplctx.keys():
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

def rewrite_single_shorthand_state_decl(data):
    '''
    Rewrite all state declarations that look like this::

      state_id_decl:
        state.func

    into::

      state_id_decl:
        state.func: []
    '''
    for sid, states in data.items():
        if isinstance(states, basestring):
            data[sid] = {states: []}


def _parent_sls(sls):
    i = sls.rfind('.')
    return sls[:i] + '.' if i != -1 else ''


def rewrite_sls_includes_excludes(data, sls):
    # if the path of the included/excluded sls starts with a leading dot(.)
    # then it's taken to be relative to the including/excluding sls.
    sls = _parent_sls(sls)
    for sid in data:
        if sid == 'include':
            includes = data[sid]
            for i, each in enumerate(includes):
                if each.startswith('.'):
                    includes[i] = sls + each[1:]
        elif sid == 'exclude':
            for d in data[sid]:
                if 'sls' in d and d['sls'].startswith('.'):
                    d['sls'] = sls + d['sls'][1:]


def _local_to_abs_sid(sid, sls):  # id must starts with '.'
    return _parent_sls(sls) + sid[1:] if '::' in sid else sls + '::' + sid[1:]


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
            name, value = nvitem.iteritems().next()
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


def statelist(states_dict, sid_excludes=set(['include', 'exclude'])):
    for sid, states in states_dict.iteritems():
        if sid in sid_excludes:
            continue
        for sname, args in states.iteritems():
            yield sid, states, sname, args


REQUISITES = set([
    'require', 'require_in', 'watch', 'watch_in', 'use', 'use_in'
])


def rename_state_ids(data, sls, is_extend=False):
    # if the .sls file is salt://my/salt/file.sls
    # then rename all state ids defined in it that start with a dot(.) with
    # "my.salt.file::" + the_state_id_without_the_first_dot.

    # update "local" references to the renamed states.

    for sid, states, _, args in statelist(data):
        if sid == 'extend' and not is_extend:
            rename_state_ids(states, sls, True)
            continue
        for req, sname, sid in nvlist2(args, REQUISITES):
            if sid.startswith('.'):
                req[sname] = _local_to_abs_sid(sid, sls)

    for sid in data.keys():
        if sid.startswith('.'):
            newsid = _local_to_abs_sid(sid, sls)
            if newsid in data:
                raise SaltRenderError(
                    'Can\'t rename state id({0}) into {1} because the later '
                    'already exists!'.format(sid, newsid)
                )
            # add a '- name: sid' to those states without '- name'.
            for args in data[sid].itervalues():
                for arg in args:
                    if isinstance(arg, dict) and iter(arg).next() == 'name':
                        break
                else: # then no '- name: ...' is defined in the state args
                    # add the sid without the leading dot as the name.
                    args.insert(0, dict(name=sid[1:]))
            data[newsid] = data[sid]
            del data[sid]


REQUIRE = set(['require', 'watch'])
REQUIRE_IN = set(['require_in', 'watch_in'])
EXTENDED_REQUIRE = {}
EXTENDED_REQUIRE_IN = {}

from itertools import chain


# To avoid cycles among states when each state requires the one before it:
#   explicit require/watch can only contain states before it
#   explicit require_in/watch_in can only contain states after it
def add_implicit_requires(data):

    def T(sid, state):
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
                    'State({0}) can\'t require/watch a state({1}) defined '
                    'after it!'.format(tag, T(rsid, rstate))
                )

        reqs = nvlist2(args, REQUIRE_IN)
        if tag in EXTENDED_REQUIRE_IN:
            reqs = chain(reqs, EXTENDED_REQUIRE_IN[tag])
        for _, rstate, rsid in reqs:
            if T(rsid, rstate) in states_before:
                raise SaltRenderError(
                    'State({0}) can\'t require_in/watch_in a state({1}) '
                    'defined before it!'.format(tag, T(rsid, rstate))
                )

        # add a (- state: sid) item, at the beginning of the require of this
        # state if there's a state before this one.
        if prev_state[0] is not None:
            try:
                nvlist(args, ['require']).next()[2].insert(0, dict([prev_state]))
            except StopIteration:  # ie, there's no require
                args.append(dict(require=[dict([prev_state])]))

        states_before.add(tag)
        prev_state = (state_name(sname), sid)


def add_goal_state(data):
    goal_sid = __opts__['stateconf_goal_state']
    if goal_sid in data:
        raise SaltRenderError(
            'Can\'t generate goal state({0})! The same state id already '
            'exists!'.format(goal_sid)
        )
    else:
        reqlist = []
        for sid, _, state, _ in \
                statelist(data, set(['include', 'exclude', 'extend'])):
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
    for state_id, state_dict in data.iteritems():
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
        for d in state_dict[key]:
            if not isinstance(d, dict):
                continue
            k, v = d.iteritems().next()
            conf[k] = v

        if not is_extend and state_id in STATE_CONF_EXT:
            extend = STATE_CONF_EXT[state_id]
            for requisite in 'require', 'watch':
                if requisite in extend:
                    extend[requisite] += to_dict[state_id].get(requisite, [])
            to_dict[state_id].update(STATE_CONF_EXT[state_id])
