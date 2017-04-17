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
from salt.utils.odict import OrderedDict
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
                     input_data='',
                     **kwargs):
    '''
    Take the path to a template and return the high data structure
    derived from the template.
    '''

    # if any error occurs, we return an empty dictionary
    ret = {}

    log.debug('compile template: {0}'.format(template))
    # We "map" env to the same as saltenv until Carbon is out in order to follow the same deprecation path
    kwargs.setdefault('env', saltenv)
    salt.utils.warn_until(
        'Carbon',
        'We are only supporting \'env\' in the templating context until Carbon comes out. '
        'Once this warning is shown, please remove the above mapping',
        _dont_call_warnings=True
    )

    if template != ':string:':
        # Template was specified incorrectly
        if not isinstance(template, string_types):
            log.error('Template was specified incorrectly: {0}'.format(template))
            return ret
        # Template does not exist
        if not os.path.isfile(template):
            log.error('Template does not exist: {0}'.format(template))
            return ret
        # Template is an empty file
        if salt.utils.is_empty(template):
            log.warn('Template is an empty file: {0}'.format(template))
            return ret

        with codecs.open(template, encoding=SLS_ENCODING) as ifile:
            # data input to the first render function in the pipe
            input_data = ifile.read()
            if not input_data.strip():
                # Template is nothing but whitespace
                log.error('Template is nothing but whitespace: {0}'.format(template))
                return ret

    # Get the list of render funcs in the render pipe line.
    render_pipe = template_shebang(template, renderers, default, input_data)

    input_data = string_io(input_data)
    for render, argline in render_pipe:
        # For GPG renderer, input_data can be an OrderedDict (from YAML) or dict (from py renderer).
        # Repress the error.
        if not isinstance(input_data, (dict, OrderedDict)):
            try:
                input_data.seek(0)
            except Exception as exp:
                log.error('error: {0}'.format(exp))

        render_kwargs = dict(renderers=renderers, tmplpath=template)
        render_kwargs.update(kwargs)
        if argline:
            render_kwargs['argline'] = argline
        start = time.time()
        ret = render(input_data, saltenv, sls, **render_kwargs)
        log.profile(
            'Time (in seconds) to render \'{0}\' using \'{1}\' renderer: {2}'.format(
                template,
                render.__module__.split('.')[-1],
                time.time() - start
            )
        )
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
                # ret is not a StringIO, which means it was rendered using
                # yaml, mako, or another engine which renders to a data
                # structure. We don't want to log this, so ignore this
                # exception.
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


def template_shebang(template, renderers, default, input_data):
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

    line = ''
    # Open up the first line of the sls template
    if template == ':string:':
        line = input_data.split()[0]
    else:
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
