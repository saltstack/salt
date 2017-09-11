# -*- coding: utf-8 -*-
'''
Manage basic template commands
'''

from __future__ import absolute_import

# Import Python libs
import time
import os
import codecs
import logging

# Import Salt libs
import salt.utils.files
import salt.utils.locales
import salt.utils.stringio
import salt.utils.versions

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import StringIO

log = logging.getLogger(__name__)


# FIXME: we should make the default encoding of a .sls file a configurable
#        option in the config, and default it to 'utf-8'.
#
SLS_ENCODING = u'utf-8'  # this one has no BOM.
SLS_ENCODER = codecs.getencoder(SLS_ENCODING)


def compile_template(template,
                     renderers,
                     default,
                     blacklist,
                     whitelist,
                     saltenv=u'base',
                     sls=u'',
                     input_data=u'',
                     **kwargs):
    '''
    Take the path to a template and return the high data structure
    derived from the template.
    '''

    # if any error occurs, we return an empty dictionary
    ret = {}

    log.debug(u'compile template: %s', template)

    if u'env' in kwargs:
        # "env" is not supported; Use "saltenv".
        kwargs.pop(u'env')

    if template != u':string:':
        # Template was specified incorrectly
        if not isinstance(template, six.string_types):
            log.error(u'Template was specified incorrectly: %s', template)
            return ret
        # Template does not exist
        if not os.path.isfile(template):
            log.error(u'Template does not exist: %s', template)
            return ret
        # Template is an empty file
        if salt.utils.files.is_empty(template):
            log.debug(u'Template is an empty file: %s', template)
            return ret

        with codecs.open(template, encoding=SLS_ENCODING) as ifile:
            # data input to the first render function in the pipe
            input_data = ifile.read()
            if not input_data.strip():
                # Template is nothing but whitespace
                log.error(u'Template is nothing but whitespace: %s', template)
                return ret

    # Get the list of render funcs in the render pipe line.
    render_pipe = template_shebang(template, renderers, default, blacklist, whitelist, input_data)

    windows_newline = u'\r\n' in input_data

    input_data = StringIO(input_data)
    for render, argline in render_pipe:
        if salt.utils.stringio.is_readable(input_data):
            input_data.seek(0)      # pylint: disable=no-member
        render_kwargs = dict(renderers=renderers, tmplpath=template)
        render_kwargs.update(kwargs)
        if argline:
            render_kwargs[u'argline'] = argline
        start = time.time()
        ret = render(input_data, saltenv, sls, **render_kwargs)
        log.profile(
            u'Time (in seconds) to render \'%s\' using \'%s\' renderer: %s',
            template,
            render.__module__.split(u'.')[-1],
            time.time() - start
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
                log.debug(
                    u'Rendered data from file: %s:\n%s',
                    template,
                    salt.utils.locales.sdecode(ret.read()))  # pylint: disable=no-member
                ret.seek(0)  # pylint: disable=no-member

    # Preserve newlines from original template
    if windows_newline:
        if salt.utils.stringio.is_readable(ret):
            is_stringio = True
            contents = ret.read()
        else:
            is_stringio = False
            contents = ret

        if isinstance(contents, six.string_types):
            if u'\r\n' not in contents:
                contents = contents.replace(u'\n', u'\r\n')
                ret = StringIO(contents) if is_stringio else contents
            else:
                if is_stringio:
                    ret.seek(0)
    return ret


def compile_template_str(template, renderers, default, blacklist, whitelist):
    '''
    Take template as a string and return the high data structure
    derived from the template.
    '''
    fn_ = salt.utils.files.mkstemp()
    with salt.utils.files.fopen(fn_, u'wb') as ofile:
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
    line = u''
    # Open up the first line of the sls template
    if template == u':string:':
        line = input_data.split()[0]
    else:
        with salt.utils.files.fopen(template, u'r') as ifile:
            line = ifile.readline()

    # Check if it starts with a shebang and not a path
    if line.startswith(u'#!') and not line.startswith(u'#!/'):
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

for comb in (u'yaml_jinja',
             u'yaml_mako',
             u'yaml_wempy',
             u'json_jinja',
             u'json_mako',
             u'json_wempy',
             u'yamlex_jinja',
             u'yamlexyamlex_mako',
             u'yamlexyamlex_wempy'):

    fmt, tmpl = comb.split(u'_')
    OLD_STYLE_RENDERERS[comb] = u'{0}|{1}'.format(tmpl, fmt)


def check_render_pipe_str(pipestr, renderers, blacklist, whitelist):
    '''
    Check that all renderers specified in the pipe string are available.
    If so, return the list of render functions in the pipe as
    (render_func, arg_str) tuples; otherwise return [].
    '''
    if pipestr is None:
        return []
    parts = [r.strip() for r in pipestr.split(u'|')]
    # Note: currently, | is not allowed anywhere in the shebang line except
    #       as pipes between renderers.

    results = []
    try:
        if parts[0] == pipestr and pipestr in OLD_STYLE_RENDERERS:
            parts = OLD_STYLE_RENDERERS[pipestr].split(u'|')
        for part in parts:
            name, argline = (part + u' ').split(u' ', 1)
            if whitelist and name not in whitelist or \
                    blacklist and name in blacklist:
                log.warning(
                    u'The renderer "%s" is disallowed by configuration and '
                    u'will be skipped.', name
                )
                continue
            results.append((renderers[name], argline.strip()))
        return results
    except KeyError:
        log.error(u'The renderer "%s" is not available', pipestr)
        return []
