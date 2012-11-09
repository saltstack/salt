# Module taken and modified from Salt's built-in yaml_mako.py renderer.
#
"""
This module provides a custom renderer that process a salt file with a
specified templating engine(eg, jinja) and a chosen data renderer(eg, yaml),
extract arguments for any ``state.config`` and provide the extracted
arguments (including salt specific args, such as 'require', etc) as template
context. The goal is to make writing reusable/configurable/ parameterized
salt files easier and cleaner.

Here's a contrived example using this renderer::

    apache.sls:
    ------------
    #!stateconf yaml.mako

    apache:
      state.config:
        - port: 80
        - source_conf: /path/to/httpd.conf

        - require_in:
          - cmd: apache_configured

    # --- end of state config ---

    apache_configured:
      cmd.run:
        - name: echo apached configured with port ${apache.port} using conf from ${apache.source_conf}
        - cwd: /


    webapp.sls:
    ------------
    #!stateconf yaml.mako

    include:
      - apache

    extend:
      apache:
        state.config:
          - port: 8080
          - source_conf: /another/path/to/httpd.conf

    webapp:
      state.config:
        - app_port: 1234 

        - require:
          - state: apache

        - require_in:
          - cmd: webapp_deployed

    # --- end of state config ---

    webapp_deployed:
      cmd.run:
        - name: echo webapp deployed into apache!
        - cwd: /


``state.config`` let's you declare and set default values for the parameters
used by your salt file. These parameters will be available in your template 
context, so you can generate the rest of your salt file according to their
values. And your parameterized salt file can be included and then extended
just like any other salt files! So, with the above two salt files, running
``state.highstate`` will actually output::

  apache configured with port 8080 using conf from /another/path/to/httpd.conf

Notice that the end of configuration marker(``# --- end of state config --``)
is needed to separate the use of 'state.config' form the rest of your salt
file, and don't forget to put the ``#!stateconf yaml.mako`` shangbang at the
beginning of your salt files. Lastly, you need to have Mako already installed,
of course. See also https://gist.github.com/1f85e4151c4fab675adb for a complete
list of features provided by this module.
"""

# TODO:
#   - names declaration is not supported...
#
#   - sls meta/info state: Eg, 
#       sls_info:
#         author: Jack Kuan
#         description: what the salt file does...
#         version: 0.1.0
#
#   - version constraint for 'include'. Eg,
#       include:
#         - apache: >= 0.1.0
#
#   - support synthetic argument? Eg, 
#
#     apache:
#       state.config:
#         - host: localhost
#         - port: 1234
#         - url: 'http://${host}:${port}/'
#
#     Currently, this won't work, but can be worked around like so:
#
#     apache:
#       state.config:
#         - host: localhost
#         - port: 1234
#     ##  - url: 'http://${host}:${port}/'
#
#     # --- end of state config ---
#     <% 
#     apache.setdefault('url', "http://%(host)s:%(port)s/" % apache)
#     %>
#

import logging
import re
import getopt
from os import path as ospath
from cStringIO import StringIO

from salt.exceptions import SaltRenderError

log = logging.getLogger(__name__)

__opts__ = {
  'stateconf_end_marker': r'#\s*-+\s*end of state config\s*-+',
  # eg, something like "# --- end of state config --" works by default.

  'stateconf_goal_state': '.goal'
  # name of the state id for the generated goal state.
}


MOD_BASENAME = ospath.basename(__file__)
INVALID_USAGE_ERROR = SaltRenderError(
  "Invalid use of %s renderer!\n"
  """Usage: #!%s [-Go] <data_renderer> [options] . <template_renderer> [options]

Options:

  -G   Do not generate the goal state that requires all other states in the sls.

  -o   Indirectly order the states by adding requires such that they will be 
       executed in the order they are defined in the sls. Implies using yaml -o.
  """ % (MOD_BASENAME, MOD_BASENAME)
)


def render(template_file, env='', sls='', argline='yaml . jinja', **kws):
    NO_GOAL_STATE = False
    IMPLICIT_REQUIRE = False

    renderers = kws['renderers']
    opts, args = getopt.getopt(argline.split(), "Go")
    argline = ' '.join(args)

    if ('-G', '') in opts:
        NO_GOAL_STATE = True

    # Split on the first dot surrounded by spaces but not preceded by a
    # backslash. A backslash preceded dot will be replaced with just dot.
    args = [ arg.strip().replace('\\.', '.') \
                for arg in re.split(r'\s+(?<!\\)\.\s+', argline, 1) ]
    try:
        name, rd_argline = (args[0]+' ').split(' ', 1)
        render_data = renderers[name] # eg, the yaml renderer
        if ('-o', '') in opts:
            if name == 'yaml':
                IMPLICIT_REQUIRE = True
                rd_argline = '-o ' + rd_argline
            else:
                raise SaltRenderError("Implicit ordering is only supported "
                                      "if the yaml renderer is used!")
        name, rt_argline = (args[1]+' ').split(' ', 1)
        render_template = renderers[name] # eg, the mako renderer
    except KeyError, e:
        raise SaltRenderError("Renderer: %s is not available!" % e)
    except IndexError, e:
        raise INVALID_USAGE_ERROR

    def process_sls_data(data, context=None, extract=False):
        ctx = dict(sls_dir=ospath.dirname(sls.replace('.', ospath.sep)))
        if context:
            ctx.update(context)
        tmplout = render_template(StringIO(data), env, sls, context=ctx,
                                  argline=rt_argline.strip()
                                  )
        data = render_data(tmplout, env, sls, argline=rd_argline.strip())
        try: 
            rewrite_sls_includes_excludes(data, sls)

            if not extract and IMPLICIT_REQUIRE:
                add_implicit_requires(data)

            if not extract and not NO_GOAL_STATE:
                add_goal_state(data)

            rename_state_ids(data, sls)

            if extract:
                extract_state_confs(data)

        except Exception:
            log.exception((
                "Error found while pre-processing the salt file, %s.\n"
                "It's likely due to a formatting error in your salt file.\n"
                "Pre-processing aborted. Stack trace:---------") % sls)
            #raise
            raise SaltRenderError("sls preprocessing/rendering failed!")
        return data

    if isinstance(template_file, basestring):
        with open(template_file, 'r') as f:
            sls_templ = f.read()
    else: # assume file-like
        sls_templ = template_file.read()

    # first pass to extract the state configuration
    match = re.search(__opts__['stateconf_end_marker'], sls_templ)
    if match:
        process_sls_data(sls_templ[:match.start()], extract=True)

    # if some config has been extracted then remove the sls-name prefix
    # of the keys in the extracted state.config context to make them easier
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
        log.debug('Rendered sls: %s' % (data,))
    return data




def _parent_sls(sls):
    i = sls.rfind('.')
    return sls[:i]+'.' if i != -1 else ''

def rewrite_sls_includes_excludes(data, sls):
    # if the path of the included/excluded sls starts with a leading dot(.) then
    # it's taken to be relative to the including/excluding sls.
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




def _local_to_abs_sid(sid, sls): # id must starts with '.'
    return _parent_sls(sls)+sid[1:] if '::' in sid else sls+'::'+sid[1:] 

def nvlist(thelist, names=None):
    """Given a list of items::

        - whatever
        - name1: value1
        - name2:
          - key: value
          - key: value

    return a generator that yields each (item, key, value) tuple, skipping
    items that are not name-value's(dictionaries) or those not in the 
    list of matching names. The item in the returned tuple is the single-key
    dictionary.
    """
    # iterate over the list under the state dict.
    for nvitem in thelist:
        if isinstance(nvitem, dict):
            # then nvitem is a name-value item(a dict) of the list.

            name, value = nvitem.iteritems().next()
            if names is None or name in names:
                yield nvitem, name, value

def nvlist2(thelist, names=None):
    """Like nvlist but applied one more time to each returned value.
    So, given a list, args,  of arguments to a state like this::

      - name: echo test
      - cwd: /
      - require:
        - file: test.sh

    nvlist2(args, ['require']) would yield the tuple,
    (dict_item, 'file', 'test.sh') where dict_item is the single-key
    dictionary of {'file': 'test.sh'}.
    
    """
    for _, _, value in nvlist(thelist, names):
        for each in nvlist(value):
            yield each

def statelist(states_dict, sid_excludes=set(['include', 'exclude'])):
    for sid, states in states_dict.iteritems():
        if sid in sid_excludes:
            continue
        for sname, args in states.iteritems():
            yield sid, states, sname, args


REQUISITES = set(['require', 'require_in', 'watch', 'watch_in', 'use', 'use_in'])
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
            data[_local_to_abs_sid(sid, sls)] = data[sid]
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
        return "%s:%s" % (sid, state_name(state))

    states_before = set()
    states_after = set()

    for sid in data:
        for state in data[sid]:
            states_after.add(T(sid, state))

    prev_state = (None, None) # (state_name, sid)
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
                        "State(%s) can't require/watch a state(%s) "
                        "defined after it!" % (tag, T(rsid, rstate)))

        reqs = nvlist2(args, REQUIRE_IN)
        if tag in EXTENDED_REQUIRE_IN:
            reqs = chain(reqs, EXTENDED_REQUIRE_IN[tag])
        for _, rstate, rsid in reqs:
            if T(rsid, rstate) in states_before:
                raise SaltRenderError(
                        "State(%s) can't require_in/watch_in a state(%s) "
                        "defined before it!" % (tag, T(rsid, rstate)))

        # add a (- state: sid) item, at the beginning of the require of this
        # state if there's a state before this one.
        if prev_state[0] is not None:
            try:
                nvlist(args, ['require']).next()[2].insert(0, dict([prev_state]))
            except StopIteration: # ie, there's no require
                args.append(dict(require=[dict([prev_state])]))

        states_before.add(tag)
        prev_state = (state_name(sname), sid)


def add_goal_state(data):
    goal_sid = __opts__['stateconf_goal_state']
    if goal_sid in data:
        return
    else:
        reqlist = []
        for sid, _, state, _ in \
                statelist(data, set(['include', 'exclude', 'extend'])):
            reqlist.append({state_name(state): sid})
        data[goal_sid] = {'state.config': [dict(require=reqlist)]}

def state_name(sname):
    """Return the name of the state regardless if sname is
    just the state name or a state.func name.
    """
    return sname.split('.', 1)[0]


# Quick and dirty way to get attribute access for dictionary keys.
# So, we can do: ${apache.port} instead of ${apache['port']} when possible.
class Bunch(dict):
    def __getattr__(self, name):
        return self[name]


# With sls:
#
#   state_id:
#     state.config:
#       - name1: value1
#
# STATE_CONF is:
#    { state_id => {name1: value1} }
#
STATE_CONF = {}       # state.config
STATE_CONF_EXT = {}   # state.config under extend: ...

def extract_state_confs(data, is_extend=False):
    for state_id, state_dict in data.iteritems():
        if state_id == 'extend' and not is_extend:
            extract_state_confs(state_dict, True)
            continue

        if 'state' in state_dict:
            key = 'state'
        elif 'state.config' in state_dict:
            key = 'state.config'
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

