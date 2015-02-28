# -*- coding: utf-8 -*-
'''
Template render systems
'''

from __future__ import absolute_import

# Import python libs
import codecs
import os
import imp
import logging
import tempfile
import traceback
import sys

# Import third party libs
import jinja2
import jinja2.ext

# Import salt libs
import salt.utils
from salt.exceptions import (
    SaltRenderError, CommandExecutionError, SaltInvocationError
)
from salt.utils.jinja import ensure_sequence_filter, show_full_context
from salt.utils.jinja import SaltCacheLoader as JinjaSaltCacheLoader
from salt.utils.jinja import SerializerExtension as JinjaSerializerExtension
from salt.utils.odict import OrderedDict
from salt import __path__ as saltpath
from salt._compat import string_types

log = logging.getLogger(__name__)


TEMPLATE_DIRNAME = os.path.join(saltpath[0], 'templates')

# FIXME: also in salt/template.py
SLS_ENCODING = 'utf-8'  # this one has no BOM.
SLS_ENCODER = codecs.getencoder(SLS_ENCODING)


def wrap_tmpl_func(render_str):

    def render_tmpl(tmplsrc,
                    from_str=False,
                    to_str=False,
                    context=None,
                    tmplpath=None,
                    **kws):

        if context is None:
            context = {}

        # We want explicit context to overwrite the **kws
        kws.update(context)
        context = kws
        assert 'opts' in context
        assert 'saltenv' in context

        if 'sls' in context:
            slspath = context['sls'].replace('.', '/')
            if tmplpath is not None:
                context['tplpath'] = tmplpath
                if not tmplpath.lower().replace('\\', '/').endswith('/init.sls'):
                    slspath = os.path.dirname(slspath)
            context['slsdotpath'] = slspath.replace('/', '.')
            context['slscolonpath'] = slspath.replace('/', ':')
            context['sls_path'] = slspath.replace('/', '_')
            context['slspath'] = slspath

        if isinstance(tmplsrc, string_types):
            if from_str:
                tmplstr = tmplsrc
            else:
                try:
                    if tmplpath is not None:
                        tmplsrc = os.path.join(tmplpath, tmplsrc)
                    with codecs.open(tmplsrc, 'r', SLS_ENCODING) as _tmplsrc:
                        tmplstr = _tmplsrc.read()
                except (UnicodeDecodeError,
                        ValueError,
                        OSError,
                        IOError) as exc:
                    if salt.utils.is_bin_file(tmplsrc):
                        # Template is a bin file, return the raw file
                        return dict(result=True, data=tmplsrc)
                    log.error(
                        'Exception occurred while reading file '
                        '{0}: {1}'.format(tmplsrc, exc),
                        # Show full traceback if debug logging is enabled
                        exc_info_on_loglevel=logging.DEBUG
                    )
                    raise exc
        else:  # assume tmplsrc is file-like.
            tmplstr = tmplsrc.read()
            tmplsrc.close()
        try:
            output = render_str(tmplstr, context, tmplpath)
            if salt.utils.is_windows():
                # Write out with Windows newlines
                output = os.linesep.join(output.splitlines())

        except SaltRenderError as exc:
            #return dict(result=False, data=str(exc))
            raise
        except Exception:
            return dict(result=False, data=traceback.format_exc())
        else:
            if to_str:  # then render as string
                return dict(result=True, data=output)
            with tempfile.NamedTemporaryFile('wb', delete=False) as outf:
                outf.write(SLS_ENCODER(output)[0])
                # Note: If nothing is replaced or added by the rendering
                #       function, then the contents of the output file will
                #       be exactly the same as the input.
            return dict(result=True, data=outf.name)

    render_tmpl.render_str = render_str
    return render_tmpl


def _get_jinja_error_slug(tb_data):
    '''
    Return the line number where the template error was found
    '''
    try:
        return [
            x
            for x in tb_data if x[2] in ('top-level template code',
                                         'template')
        ][-1]
    except IndexError:
        pass


def _get_jinja_error_message(tb_data):
    '''
    Return an understandable message from jinja error output
    '''
    try:
        line = _get_jinja_error_slug(tb_data)
        return u'{0}({1}):\n{3}'.format(*line)
    except IndexError:
        pass
    return None


def _get_jinja_error_line(tb_data):
    '''
    Return the line number where the template error was found
    '''
    try:
        return _get_jinja_error_slug(tb_data)[1]
    except IndexError:
        pass
    return None


def _get_jinja_error(trace, context=None):
    '''
    Return the error line and error message output from
    a stacktrace.
    If we are in a macro, also output inside the message the
    exact location of the error in the macro
    '''
    if not context:
        context = {}
    out = ''
    error = _get_jinja_error_slug(trace)
    line = _get_jinja_error_line(trace)
    msg = _get_jinja_error_message(trace)
    # if we failed on a nested macro, output a little more info
    # to help debugging
    # if sls is not found in context, add output only if we can
    # resolve the filename
    add_log = False
    template_path = None
    if 'sls' not in context:
        if (
            (error[0] != '<unknown>')
            and os.path.exists(error[0])
        ):
            template_path = error[0]
            add_log = True
    else:
        # the offender error is not from the called sls
        filen = context['sls'].replace('.', '/')
        if (
            not error[0].endswith(filen)
            and os.path.exists(error[0])
        ):
            add_log = True
            template_path = error[0]
    # if we add a log, format explicitly the exeception here
    # by telling to output the macro context after the macro
    # error log place at the beginning
    if add_log:
        if template_path:
            out = '\n{0}\n'.format(msg.splitlines()[0])
            out += salt.utils.get_context(
                salt.utils.fopen(template_path).read(),
                line,
                marker='    <======================')
        else:
            out = '\n{0}\n'.format(msg)
        line = 0
    return line, out


def render_jinja_tmpl(tmplstr, context, tmplpath=None):
    opts = context['opts']
    saltenv = context['saltenv']
    loader = None
    newline = False

    if tmplstr and not isinstance(tmplstr, unicode):
        # http://jinja.pocoo.org/docs/api/#unicode
        tmplstr = tmplstr.decode(SLS_ENCODING)

    if tmplstr.endswith('\n'):
        newline = True

    if not saltenv:
        if tmplpath:
            # ie, the template is from a file outside the state tree
            #
            # XXX: FileSystemLoader is not being properly instantiated here is
            # it? At least it ain't according to:
            #
            #   http://jinja.pocoo.org/docs/api/#jinja2.FileSystemLoader
            loader = jinja2.FileSystemLoader(
                context, os.path.dirname(tmplpath))
    else:
        loader = JinjaSaltCacheLoader(opts, saltenv, pillar_rend=context.get('_pillar_rend', False))

    env_args = {'extensions': [], 'loader': loader}

    if hasattr(jinja2.ext, 'with_'):
        env_args['extensions'].append('jinja2.ext.with_')
    if hasattr(jinja2.ext, 'do'):
        env_args['extensions'].append('jinja2.ext.do')
    if hasattr(jinja2.ext, 'loopcontrols'):
        env_args['extensions'].append('jinja2.ext.loopcontrols')
    env_args['extensions'].append(JinjaSerializerExtension)

    # Pass through trim_blocks and lstrip_blocks Jinja parameters
    # trim_blocks removes newlines around Jinja blocks
    # lstrip_blocks strips tabs and spaces from the beginning of
    # line to the start of a block.
    if opts.get('jinja_trim_blocks', False):
        log.debug('Jinja2 trim_blocks is enabled')
        env_args['trim_blocks'] = True
    if opts.get('jinja_lstrip_blocks', False):
        log.debug('Jinja2 lstrip_blocks is enabled')
        env_args['lstrip_blocks'] = True

    if opts.get('allow_undefined', False):
        jinja_env = jinja2.Environment(**env_args)
    else:
        jinja_env = jinja2.Environment(undefined=jinja2.StrictUndefined,
                                       **env_args)

    jinja_env.filters['strftime'] = salt.utils.date_format
    jinja_env.filters['sequence'] = ensure_sequence_filter

    jinja_env.globals['odict'] = OrderedDict
    jinja_env.globals['show_full_context'] = show_full_context

    decoded_context = {}
    for key, value in context.iteritems():
        if not isinstance(value, string_types):
            decoded_context[key] = value
            continue
        decoded_context[key] = salt.utils.sdecode(value)

    try:
        template = jinja_env.from_string(tmplstr)
        template.globals.update(decoded_context)
        output = template.render(**decoded_context)
    except jinja2.exceptions.TemplateSyntaxError as exc:
        trace = traceback.extract_tb(sys.exc_info()[2])
        line, out = _get_jinja_error(trace, context=decoded_context)
        if not line:
            tmplstr = ''
        raise SaltRenderError('Jinja syntax error: {0}{1}'.format(exc, out),
                              line,
                              tmplstr)
    except jinja2.exceptions.UndefinedError as exc:
        trace = traceback.extract_tb(sys.exc_info()[2])
        out = _get_jinja_error(trace, context=decoded_context)[1]
        tmplstr = ''
        # Don't include the line number, since it is misreported
        # https://github.com/mitsuhiko/jinja2/issues/276
        raise SaltRenderError(
            'Jinja variable {0}{1}'.format(
                exc, out),
            buf=tmplstr)
    except (SaltInvocationError, CommandExecutionError) as exc:
        trace = traceback.extract_tb(sys.exc_info()[2])
        line, out = _get_jinja_error(trace, context=decoded_context)
        if not line:
            tmplstr = ''
        raise SaltRenderError(
            'Problem running salt function in Jinja template: {0}{1}'.format(
                exc, out),
            line,
            tmplstr)
    except Exception as exc:
        tracestr = traceback.format_exc()
        trace = traceback.extract_tb(sys.exc_info()[2])
        line, out = _get_jinja_error(trace, context=decoded_context)
        if not line:
            tmplstr = ''
        else:
            tmplstr += '\n{0}'.format(tracestr)
        raise SaltRenderError('Jinja error: {0}{1}'.format(exc, out),
                              line,
                              tmplstr,
                              trace=tracestr)

    # Workaround a bug in Jinja that removes the final newline
    # (https://github.com/mitsuhiko/jinja2/issues/75)
    if newline:
        output += '\n'

    return output


def render_mako_tmpl(tmplstr, context, tmplpath=None):
    import mako.exceptions
    from mako.template import Template
    from salt.utils.mako import SaltMakoTemplateLookup

    saltenv = context['saltenv']
    lookup = None
    if not saltenv:
        if tmplpath:
            # ie, the template is from a file outside the state tree
            from mako.lookup import TemplateLookup
            lookup = TemplateLookup(directories=[os.path.dirname(tmplpath)])
    else:
        lookup = SaltMakoTemplateLookup(context['opts'], saltenv)
    try:
        return Template(
            tmplstr,
            strict_undefined=True,
            uri=context['sls'].replace('.', '/') if 'sls' in context else None,
            lookup=lookup
        ).render(**context)
    except:
        raise SaltRenderError(mako.exceptions.text_error_template().render())


def render_wempy_tmpl(tmplstr, context, tmplpath=None):
    from wemplate.wemplate import TemplateParser as Template
    return Template(tmplstr).render(**context)


def py(sfn, string=False, **kwargs):  # pylint: disable=C0103
    '''
    Render a template from a python source file

    Returns::

        {'result': bool,
         'data': <Error data or rendered file path>}
    '''
    if not os.path.isfile(sfn):
        return {}

    mod = imp.load_source(
            os.path.basename(sfn).split('.')[0],
            sfn
            )
    for kwarg in kwargs:
        setattr(mod, kwarg, kwargs[kwarg])

    try:
        data = mod.run()
        if string:
            return {'result': True,
                    'data': data}
        tgt = salt.utils.mkstemp()
        with salt.utils.fopen(tgt, 'w+') as target:
            target.write(data)
        return {'result': True,
                'data': tgt}
    except Exception:
        trb = traceback.format_exc()
        return {'result': False,
                'data': trb}


JINJA = wrap_tmpl_func(render_jinja_tmpl)
MAKO = wrap_tmpl_func(render_mako_tmpl)
WEMPY = wrap_tmpl_func(render_wempy_tmpl)

TEMPLATE_REGISTRY = {
    'jinja': JINJA,
    'mako': MAKO,
    'py': py,
    'wempy': WEMPY,
}
