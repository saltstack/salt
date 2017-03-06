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
import salt.utils.files
import salt.utils.stringio
from salt._compat import string_io

# Import 3rd-party libs
import salt.ext.six as six
log = logging.getLogger(__name__)


# FIXME: we should make the default encoding of a .sls file a configurable
#        option in the config, and default it to 'utf-8'.
#
SLS_ENCODING = 'utf-8'  # this one has no BOM.
SLS_ENCODER = codecs.getencoder(SLS_ENCODING)


def compile_template(template,
                     renderers,
                     default,
                     blacklist,
                     whitelist,
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

    if 'env' in kwargs:
        salt.utils.warn_until(
            'Oxygen',
            'Parameter \'env\' has been detected in the argument list.  This '
            'parameter is no longer used and has been replaced by \'saltenv\' '
            'as of Salt 2016.11.0.  This warning will be removed in Salt Oxygen.'
            )
        kwargs.pop('env')

    if template != ':string:':
        # Template was specified incorrectly
        if not isinstance(template, six.string_types):
            log.error('Template was specified incorrectly: {0}'.format(template))
            return ret
        # Template does not exist
        if not os.path.isfile(template):
            log.error('Template does not exist: {0}'.format(template))
            return ret
        # Template is an empty file
        if salt.utils.is_empty(template):
            log.debug('Template is an empty file: {0}'.format(template))
            return ret

        with codecs.open(template, encoding=SLS_ENCODING) as ifile:
            # data input to the first render function in the pipe
            input_data = ifile.read()
            if not input_data.strip():
                # Template is nothing but whitespace
                log.error('Template is nothing but whitespace: {0}'.format(template))
                return ret

    # Get the list of render funcs in the render pipe line.
    render_pipe = template_shebang(template, renderers, default, blacklist, whitelist, input_data)

    input_data = string_io(input_data)
    for render, argline in render_pipe:
        if salt.utils.stringio.is_readable(input_data):
            input_data.seek(0)      # pylint: disable=no-member
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
            # If ret is not a StringIO (which means it was rendered using
            # yaml, mako, or another engine which renders to a data
            # structure) we don't want to log this.
            if salt.utils.stringio.is_readable(ret):
                log.debug('Rendered data from file: {0}:\n{1}'.format(
                    template,
                    ret.read()))    # pylint: disable=no-member
                ret.seek(0)         # pylint: disable=no-member
    return ret


def compile_template_str(template, renderers, default, blacklist, whitelist):
    '''
    Take template as a string and return the high data structure
    derived from the template.
    '''
    fn_ = salt.utils.files.mkstemp()
    with salt.utils.fopen(fn_, 'wb') as ofile:
        ofile.write(SLS_ENCODER(template)[0])
    return compile_template(fn_, renderers, default, blacklist, whitelist)


def template_shebang(template, renderers, default, blacklist, whitelist, input_data):
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
        # If the shebang does not contain recognized/not-blacklisted/whitelisted
        # renderers, do not fall back to the default renderer
        return check_render_pipe_str(line.strip()[2:], renderers, blacklist, whitelist)
    else:
        return check_render_pipe_str(default, renderers, blacklist, whitelist)


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


def check_render_pipe_str(pipestr, renderers, blacklist, whitelist):
    '''
    Check that all renderers specified in the pipe string are available.
    If so, return the list of render functions in the pipe as
    (render_func, arg_str) tuples; otherwise return [].
    '''
    if pipestr is None:
        return []
    parts = [r.strip() for r in pipestr.split('|')]
    # Note: currently, | is not allowed anywhere in the shebang line except
    #       as pipes between renderers.

    results = []
    try:
        if parts[0] == pipestr and pipestr in OLD_STYLE_RENDERERS:
            parts = OLD_STYLE_RENDERERS[pipestr].split('|')
        for part in parts:
            name, argline = (part + ' ').split(' ', 1)
            if whitelist and name not in whitelist or \
                    blacklist and name in blacklist:
                log.warning('The renderer "{0}" is disallowed by cofiguration and will be skipped.'.format(name))
                continue
            results.append((renderers[name], argline.strip()))
        return results
    except KeyError:
        log.error('The renderer "{0}" is not available'.format(pipestr))
        return []
