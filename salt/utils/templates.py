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
import salt.exceptions
from salt.utils.jinja import SaltCacheLoader as JinjaSaltCacheLoader
from salt.utils.jinja import SerializerExtension as JinjaSerializerExtension

log = logging.getLogger(__name__)


class SaltTemplateRenderError(salt.exceptions.SaltException):
    pass


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
        assert 'env' in context

        if isinstance(tmplsrc, basestring):
            if from_str:
                tmplstr = tmplsrc
            else:
                try:
                    with codecs.open(tmplsrc, 'r', SLS_ENCODING) as _tmplsrc:
                        tmplstr = _tmplsrc.read()
                except (UnicodeDecodeError, ValueError) as exc:
                    if salt.utils.is_bin_file(tmplsrc):
                        # Template is a bin file, return the raw file
                        return dict(result=True, data=tmplsrc)
                    log.error(
                        'Exception occurred while reading file '
                        '{0}: {1}'.format(tmplsrc, exc),
                        # Show full traceback if debug logging is enabled
                        exc_info=log.isEnabledFor(logging.DEBUG)
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

        except SaltTemplateRenderError as exc:
            return dict(result=False, data=str(exc))
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


def render_jinja_tmpl(tmplstr, context, tmplpath=None):
    opts = context['opts']
    env = context['env']
    loader = None
    newline = False

    if tmplstr and not isinstance(tmplstr, unicode):
        # http://jinja.pocoo.org/docs/api/#unicode
        tmplstr = tmplstr.decode(SLS_ENCODING)

    if tmplstr.endswith('\n'):
        newline = True

    if not env:
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
        loader = JinjaSaltCacheLoader(opts, context['env'])

    env_args = {'extensions': [], 'loader': loader}

    if hasattr(jinja2.ext, 'with_'):
        env_args['extensions'].append('jinja2.ext.with_')
    if hasattr(jinja2.ext, 'do'):
        env_args['extensions'].append('jinja2.ext.do')
    if hasattr(jinja2.ext, 'loopcontrols'):
        env_args['extensions'].append('jinja2.ext.loopcontrols')
    env_args['extensions'].append(JinjaSerializerExtension)

    if opts.get('allow_undefined', False):
        jinja_env = jinja2.Environment(**env_args)
    else:
        jinja_env = jinja2.Environment(undefined=jinja2.StrictUndefined,
                                       **env_args)

    jinja_env.filters['strftime'] = salt.utils.date_format

    unicode_context = {}
    for key, value in context.iteritems():
        if not isinstance(value, basestring):
            unicode_context[key] = value
            continue

        # Let's try UTF-8 and fail if this still fails, that's why this is not
        # wrapped in a try/except
        unicode_context[key] = unicode(value, 'utf-8')

    try:
        output = jinja_env.from_string(tmplstr).render(**unicode_context)
    except jinja2.exceptions.TemplateSyntaxError as exc:
        line = traceback.extract_tb(sys.exc_info()[2])[-1][1]
        marker = '    <======================'
        context = get_template_context(tmplstr, line, marker=marker)
        error = '{0}; line {1} in template:\n\n{2}'.format(
                exc,
                line,
                context
        )
        raise SaltTemplateRenderError(error)
    except jinja2.exceptions.UndefinedError:
        line = traceback.extract_tb(sys.exc_info()[2])[-1][1]
        marker = '    <======================'
        context = get_template_context(tmplstr, line, marker=marker)
        error = 'Undefined jinja variable; line {0} in template\n\n{1}'.format(
                line,
                context
        )
        raise SaltTemplateRenderError(error)

    # Workaround a bug in Jinja that removes the final newline
    # (https://github.com/mitsuhiko/jinja2/issues/75)
    if newline:
        output += '\n'

    return output


def render_mako_tmpl(tmplstr, context, tmplpath=None):
    import mako.exceptions
    from mako.template import Template
    from salt.utils.mako import SaltMakoTemplateLookup

    env = context['env']
    lookup = None
    if not env:
        if tmplpath:
            # ie, the template is from a file outside the state tree
            from mako.lookup import TemplateLookup
            lookup = TemplateLookup(directories=[os.path.dirname(tmplpath)])
    else:
        lookup = SaltMakoTemplateLookup(context['opts'], context['env'])
    try:
        return Template(
            tmplstr,
            strict_undefined=True,
            uri=context['sls'].replace('.', '/') if 'sls' in context else None,
            lookup=lookup
        ).render(**context)
    except:
        raise SaltTemplateRenderError(
                    mako.exceptions.text_error_template().render())


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


def get_template_context(template, line, num_lines=5, marker=None):
    """Returns debugging context around a line in a given template.

    Returns:: string
    """
    template_lines = template.splitlines()
    num_template_lines = len(template_lines)

    # in test, a single line template would return a crazy line number like,
    # 357.  do this sanity check and if the given line is obviously wrong, just
    # return the entire template
    if line > num_template_lines:
        return template

    context_start = max(0, line-num_lines-1)  # subtract 1 for 0-based indexing
    context_end = min(num_template_lines, line+num_lines)
    error_line_in_context = line - context_start - 1  # subtract 1 for 0-based indexing

    buf = []
    if context_start > 0:
        buf.append('[...]')
        error_line_in_context += 1

    buf.extend(template_lines[context_start:context_end])

    if context_end < num_template_lines:
        buf.append('[...]')

    if marker:
        buf[error_line_in_context] += marker

    return '---\n{0}\n---'.format('\n'.join(buf))


JINJA = wrap_tmpl_func(render_jinja_tmpl)
MAKO = wrap_tmpl_func(render_mako_tmpl)
WEMPY = wrap_tmpl_func(render_wempy_tmpl)

TEMPLATE_REGISTRY = {
    'jinja': JINJA,
    'mako': MAKO,
    'py': py,
    'wempy': WEMPY,
}
