'''
Manage basic template commands
'''
# Import python libs
import time
import os
import tempfile
import codecs
from cStringIO import StringIO as cStringIO
from StringIO import StringIO as pyStringIO

# Import salt libs
import salt.utils
from salt._compat import string_types


def StringIO(s=None):  # cStringIO can't handle unicode
    try:
        return cStringIO(bytes(s))
    except UnicodeEncodeError:
        return pyStringIO(s)

#FIXME: we should make the default encoding of a .sls file a configurable
#       option in the config, and default it to 'utf-8'.
#
sls_encoding = 'utf-8'  # this one has no BOM.
sls_encoder = codecs.getencoder(sls_encoding)


def compile_template(template, renderers, default, env='', sls=''):
    '''
    Take the path to a template and return the high data structure
    derived from the template.
    '''
    # Template was specified incorrectly
    if not isinstance(template, string_types):
        return {}
    # Template does not exists
    if not os.path.isfile(template):
        return {}
    # Template is an empty file
    if salt.utils.is_empty(template):
        return {}

    # Get the list of render funcs in the render pipe line.
    render_pipe = template_shebang(template, renderers, default)

    with codecs.open(template, encoding=sls_encoding) as f:
        # data input to the first render function in the pipe
        input_data = f.read()
        if not input_data.strip():
            # Template is nothing but whitespace
            return {}

    input_data = StringIO(input_data)
    for render, argline in render_pipe:
        if argline:
            render_kwargs = dict(renderers=renderers, argline=argline)
        else:
            render_kwargs = dict(renderers=renderers)
        ret = render(input_data, env, sls, **render_kwargs)
        if ret is None:
            # The file is empty or is being written elsewhere
            time.sleep(0.01)
            ret = render(input_data, env, sls, **render_kwargs)
        input_data = ret
    return ret


def compile_template_str(template, renderers, default):
    '''
    Take template as a string and return the high data structure
    derived from the template.
    '''
    fn_ = salt.utils.mkstemp()
    with open(fn_, 'w+') as f:
        f.write(sls_encoder(template)[0])
    return compile_template(fn_, renderers, default)


def template_shebang(template, renderers, default):
    '''
    Check the template shebang line and return the list of renderers specified
    in the pipe.

    Example shebang lines::

      #!yaml_jinja
      #!yaml_mako
      #!mako|yaml
      #!jinja|yaml
      #!jinja|mako|yaml
      #!mako|yaml|stateconf
      #!jinja|yaml|stateconf
      #!mako|yaml_odict
      #!mako|yaml_odict|stateconf

    '''
    render_pipe = []

    # Open up the first line of the sls template
    with open(template, 'r') as f:
        line = f.readline()

        # Check if it starts with a shebang
        if line.startswith('#!'):

            # pull out the shebang data
            render_pipe = check_render_pipe_str(line.strip()[2:], renderers)

    if not render_pipe:
        render_pipe = check_render_pipe_str(default, renderers)

    return render_pipe




# A dict of combined renderer(ie, rend1_rend2_...) to
# render-pipe(ie, rend1|rend2|...)
#
OLD_STYLE_RENDERERS = {}
for comb in """
    yaml_jinja
    yaml_mako
    yaml_wempy
    json_jinja
    json_mako
    json_wempy
    """.strip().split():

    fmt, tmpl = comb.split('_')
    OLD_STYLE_RENDERERS[comb] = "%s|%s" % (tmpl, fmt)


def check_render_pipe_str(pipestr, renderers):
    '''
    Check that all renderers specified in the pipe string are available.
    If so, return the list of render functions in the pipe as (render_func, arg_str)
    tuples; otherwise return [].
    '''
    parts = [r.strip() for r in pipestr.split('|')]
    # Note: currently, | is not allowed anywhere in the shebang line except
    #       as pipes between renderers.

    results = []
    try:
        if parts[0] == pipestr and pipestr in OLD_STYLE_RENDERERS:
            parts = OLD_STYLE_RENDERERS[pipestr].split('|')
        for p in parts:
            name, argline = (p+' ').split(' ', 1)
            results.append((renderers[name], argline.strip()))
        return results
    except KeyError:
        return []

