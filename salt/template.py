# -*- coding: utf-8 -*-
'''
Manage basic template commands
'''

from __future__ import absolute_import

# Import python libs
import time
import os
import codecs
import logging

# Import salt libs
import salt.utils
from salt._compat import string_io
from salt.ext.six import string_types

log = logging.getLogger(__name__)


#FIXME: we should make the default encoding of a .sls file a configurable
#       option in the config, and default it to 'utf-8'.
#
SLS_ENCODING = 'utf-8'  # this one has no BOM.
SLS_ENCODER = codecs.getencoder(SLS_ENCODING)


def compile_template(template,
                     renderers,
                     default,
                     saltenv='base',
                     sls='',
                     **kwargs):
    '''
    Take the path to a template and return the high data structure
    derived from the template.
    '''

    # We "map" env to the same as saltenv until Boron is out in order to follow the same deprecation path
    kwargs.setdefault('env', saltenv)
    salt.utils.warn_until(
        'Boron',
        'We are only supporting \'env\' in the templating context until Boron comes out. '
        'Once this warning is shown, please remove the above mapping',
        _dont_call_warnings=True
    )

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

    with codecs.open(template, encoding=SLS_ENCODING) as ifile:
        # data input to the first render function in the pipe
        input_data = ifile.read()
        if not input_data.strip():
            # Template is nothing but whitespace
            return {}

    input_data = string_io(input_data)
    for render, argline in render_pipe:
        try:
            input_data.seek(0)
        except Exception:
            pass
        render_kwargs = dict(renderers=renderers, tmplpath=template)
        render_kwargs.update(kwargs)
        if argline:
            render_kwargs['argline'] = argline
        ret = render(input_data, saltenv, sls, **render_kwargs)
        if ret is None:
            # The file is empty or is being written elsewhere
            time.sleep(0.01)
            ret = render(input_data, saltenv, sls, **render_kwargs)
        input_data = ret
        if log.isEnabledFor(logging.GARBAGE):  # pylint: disable=no-member
            try:
                log.debug('Rendered data from file: {0}:\n{1}'.format(
                    template,
                    ret.read()))
                ret.seek(0)
            except Exception:
                pass
    return ret


def compile_template_str(template, renderers, default):
    '''
    Take template as a string and return the high data structure
    derived from the template.
    '''
    fn_ = salt.utils.mkstemp()
    with salt.utils.fopen(fn_, 'wb') as ofile:
        ofile.write(SLS_ENCODER(template)[0])
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
    with salt.utils.fopen(template, 'r') as ifile:
        line = ifile.readline()

        # Check if it starts with a shebang and not a path
        if line.startswith('#!') and not line.startswith('#!/'):

            # pull out the shebang data
            render_pipe = check_render_pipe_str(line.strip()[2:], renderers)

    if not render_pipe:
        render_pipe = check_render_pipe_str(default, renderers)

    return render_pipe


# A dict of combined renderer (i.e., rend1_rend2_...) to
# render-pipe (i.e., rend1|rend2|...)
#
OLD_STYLE_RENDERERS = {}

for comb in '''
        yaml_jinja
        yaml_mako
        yaml_wempy
        json_jinja
        json_mako
        json_wempy
        yamlex_jinja
        yamlexyamlex_mako
        yamlexyamlex_wempy
        '''.strip().split():

    fmt, tmpl = comb.split('_')
    OLD_STYLE_RENDERERS[comb] = '{0}|{1}'.format(tmpl, fmt)


def check_render_pipe_str(pipestr, renderers):
    '''
    Check that all renderers specified in the pipe string are available.
    If so, return the list of render functions in the pipe as
    (render_func, arg_str) tuples; otherwise return [].
    '''
    parts = [r.strip() for r in pipestr.split('|')]
    # Note: currently, | is not allowed anywhere in the shebang line except
    #       as pipes between renderers.

    results = []
    try:
        if parts[0] == pipestr and pipestr in OLD_STYLE_RENDERERS:
            parts = OLD_STYLE_RENDERERS[pipestr].split('|')
        for part in parts:
            name, argline = (part + ' ').split(' ', 1)
            results.append((renderers[name], argline.strip()))
        return results
    except KeyError:
        log.error('The renderer "{0}" is not available'.format(pipestr))
        return []
