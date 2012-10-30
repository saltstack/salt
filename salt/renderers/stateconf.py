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
#   - Generate a sls goal state that requires all the other states in the
#     salt file.
#
#   - Optionally, add require's to states in the salt file to enforce
#     the execution of the states in the order they are defined in the salt
#     file. (use orderded dict for yaml map)
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
import warnings
import re
from os import path as ospath
from cStringIO import StringIO

from salt.exceptions import SaltRenderError

log = logging.getLogger(__name__)

__opts__ = {
  'stateconf_end_marker': r'#\s*-+\s*end of state config\s*-+',
  # eg, something like "# --- end of state config --" works by default.
}


MOD_BASENAME = ospath.basename(__file__)
INVALID_USAGE_ERROR = SaltRenderError(
    "Invalid use of %s renderer! "
    "Usage: #!%s <data_renderer>.<template_renderer>" % (
         MOD_BASENAME, MOD_BASENAME))


def render(template_file, env='', sls='', argline='yaml.jinja', **kws):
    renderers = kws['renderers']
    try:
        args = [ arg.strip() for arg in argline.split('.') ]
    except:
        raise INVALID_USAGE_ERROR
    try:
        render_data = renderers[args[0]] # eg, the yaml renderer
        render_template = renderers[args[1]] # eg, the mako renderer
    except KeyError, e:
        raise SaltRenderError("Renderer: %s is not available!" % e)
    except IndexError, e:
        raise INVALID_USAGE_ERROR


    def process_sls_data(data, context=None):
        if not context:
            match = re.search(__opts__['stateconf_end_marker'], data)
            if match:
                data = data[:match.start()]
        
        data = render_data(
                   render_template(StringIO(data), env, sls, context=context),
                   env, sls)
        try: 
            rewrite_sls_includes_excludes(data, sls)
            rename_state_ids(data, sls)
            if not context:
                extract_state_confs(data)
        except Exception:
            log.exception((
                "Error found while pre-processing the salt file, %s.\n"
                "It's likely due to a formatting error in your salt file.\n"
                "Pre-processing aborted. Stack trace:---------") % sls)

            # not raising the error because ususally if something went wrong
            # with the rendering then the rendered result will contain errors,
            # which salt will complain anyway.
        return data

    if isinstance(template_file, basestring):
        with open(template_file, 'r') as f:
            sls_templ = f.read()
    else: # assume file-like
        sls_templ = template_file.read()

    # first pass to extract the state configuration
    data = process_sls_data(sls_templ)

    # if some config has been extracted then
    # do a second pass that provides the extracted conf as template context
    if STATE_CONF:  

        # but first remove the sls-name prefix of the keys in the extracted
        # state.config context to make them easier to use in the salt file.
        tmplctx = STATE_CONF.copy()
        prefix = sls + '::'
        for k in tmplctx.keys():
            if k.startswith(prefix):
                tmplctx[k[len(prefix):]] = tmplctx[k]
                del tmplctx[k]

        data = process_sls_data(sls_templ, tmplctx)

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



RESERVED_SIDS = set(['include', 'exclude'])
REQUISITES = set(['require', 'require_in', 'watch', 'watch_in', 'use', 'use_in'])

def _local_to_abs_sid(sid, sls): # id must starts with '.'
    return _parent_sls(sls)+sid[1:] if '::' in sid else sls+'::'+sid[1:] 

def rename_state_ids(data, sls, is_extend=False):
    # if the .sls file is salt://my/salt/file.sls
    # then rename all state ids defined in it that start with a dot(.) with
    # "my.salt.file::" + the_state_id_without_the_first_dot.

    # update "local" references to the renamed states.
    for sid, states in data.items():
        if sid in RESERVED_SIDS:
            continue

        if sid == 'extend' and not is_extend:
            rename_state_ids(states, sls, True)
            continue

        for args in states.itervalues():
            for name, value in (nv.iteritems().next() for nv in args):
                if name not in REQUISITES:
                    continue
                for req in value:
                    sid = req.itervalues().next()
                    if sid.startswith('.'):
                        req[req.iterkeys().next()] = _local_to_abs_sid(sid, sls)

    for sid in data.keys():
        if sid.startswith('.'):
            data[_local_to_abs_sid(sid, sls)] = data[sid]
            del data[sid]




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
            k, v = d.iteritems().next()
            conf[k] = v

        if not is_extend and state_id in STATE_CONF_EXT:
            extend = STATE_CONF_EXT[state_id]
            for requisite in 'require', 'watch':
                if requisite in extend:
                    extend[requisite] += to_dict[state_id].get(requisite, [])
            to_dict[state_id].update(STATE_CONF_EXT[state_id])

