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
import salt.ext.six as six

# Import salt libs
import salt.utils
import salt.utils.http
import salt.utils.files
import salt.utils.yamlencoding
import salt.utils.locales
import salt.utils.hashutils
from salt.exceptions import (
    SaltRenderError, CommandExecutionError, SaltInvocationError
)
import salt.utils.jinja
import salt.utils.network
from salt.utils.odict import OrderedDict
from salt import __path__ as saltpath

log = logging.getLogger(__name__)


TEMPLATE_DIRNAME = os.path.join(saltpath[0], 'templates')

# FIXME: also in salt/template.py
SLS_ENCODING = 'utf-8'  # this one has no BOM.
SLS_ENCODER = codecs.getencoder(SLS_ENCODING)


class AliasedLoader(object):
    '''
    Light wrapper around the LazyLoader to redirect 'cmd.run' calls to
    'cmd.shell', for easy use of shellisms during templating calls

    Dotted aliases ('cmd.run') must resolve to another dotted alias
    (e.g. 'cmd.shell')

    Non-dotted aliases ('cmd') must resolve to a dictionary of function
    aliases for that module (e.g. {'run': 'shell'})
    '''

    def __init__(self, wrapped):
        self.wrapped = wrapped

    def __getitem__(self, name):
        return self.wrapped[name]

    def __getattr__(self, name):
        return getattr(self.wrapped, name)


class AliasedModule(object):
    '''
    Light wrapper around module objects returned by the LazyLoader's getattr
    for the purposes of `salt.cmd.run()` syntax in templates

    Allows for aliasing specific functions, such as `run` to `shell` for easy
    use of shellisms during templating calls
    '''
    def __init__(self, wrapped, aliases):
        self.aliases = aliases
        self.wrapped = wrapped

    def __getattr__(self, name):
        return getattr(self.wrapped, name)


def wrap_tmpl_func(render_str):

    def render_tmpl(tmplsrc,
                    from_str=False,
                    to_str=False,
                    context=None,
                    tmplpath=None,
                    **kws):

        if context is None:
            context = {}

        # Alias cmd.run to cmd.shell to make python_shell=True the default for
        # templated calls
        if 'salt' in kws:
            kws['salt'] = AliasedLoader(kws['salt'])

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
                template = tmplpath.replace('\\', '/')
                i = template.rfind(slspath.replace('.', '/'))
                if i != -1:
                    template = template[i:]
                tpldir = os.path.dirname(template).replace('\\', '/')
                tpldata = {
                    'tplfile': template,
                    'tpldir': '.' if tpldir == '' else tpldir,
                    'tpldot': tpldir.replace('/', '.'),
                }
                context.update(tpldata)
            context['slsdotpath'] = slspath.replace('/', '.')
            context['slscolonpath'] = slspath.replace('/', ':')
            context['sls_path'] = slspath.replace('/', '_')
            context['slspath'] = slspath

        if isinstance(tmplsrc, six.string_types):
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
            if six.PY2:
                output = output.encode(SLS_ENCODING)
            if salt.utils.is_windows():
                # Write out with Windows newlines
                output = os.linesep.join(output.splitlines())

        except SaltRenderError as exc:
            log.error("Rendering exception occurred: {0}".format(exc))
            #return dict(result=False, data=str(exc))
            raise
        except Exception:
            return dict(result=False, data=traceback.format_exc())
        else:
            if to_str:  # then render as string
                return dict(result=True, data=output)
            with tempfile.NamedTemporaryFile('wb', delete=False, prefix=salt.utils.files.TEMPFILE_PREFIX) as outf:
                if six.PY3:
                    output = output.encode(SLS_ENCODING)
                outf.write(output)
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
            with salt.utils.fopen(template_path) as fp_:
                template_contents = fp_.read()
            out += salt.utils.get_context(
                template_contents,
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

    if tmplstr and not isinstance(tmplstr, six.text_type):
        # http://jinja.pocoo.org/docs/api/#unicode
        tmplstr = tmplstr.decode(SLS_ENCODING)

    if tmplstr.endswith('\n'):
        newline = True

    if not saltenv:
        if tmplpath:
            # i.e., the template is from a file outside the state tree
            #
            # XXX: FileSystemLoader is not being properly instantiated here is
            # it? At least it ain't according to:
            #
            #   http://jinja.pocoo.org/docs/api/#jinja2.FileSystemLoader
            loader = jinja2.FileSystemLoader(
                context, os.path.dirname(tmplpath))
    else:
        loader = salt.utils.jinja.SaltCacheLoader(opts, saltenv, pillar_rend=context.get('_pillar_rend', False))

    env_args = {'extensions': [], 'loader': loader}

    if hasattr(jinja2.ext, 'with_'):
        env_args['extensions'].append('jinja2.ext.with_')
    if hasattr(jinja2.ext, 'do'):
        env_args['extensions'].append('jinja2.ext.do')
    if hasattr(jinja2.ext, 'loopcontrols'):
        env_args['extensions'].append('jinja2.ext.loopcontrols')
    env_args['extensions'].append(salt.utils.jinja.SerializerExtension)

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
    jinja_env.filters['sequence'] = salt.utils.jinja.ensure_sequence_filter
    jinja_env.filters['http_query'] = salt.utils.http.query
    jinja_env.filters['to_bool'] = salt.utils.jinja.to_bool
    jinja_env.filters['exactly_n_true'] = salt.utils.exactly_n
    jinja_env.filters['exactly_one_true'] = salt.utils.exactly_one
    jinja_env.filters['quote'] = salt.utils.jinja.quote
    jinja_env.filters['regex_search'] = salt.utils.jinja.regex_search
    jinja_env.filters['regex_match'] = salt.utils.jinja.regex_match
    jinja_env.filters['regex_replace'] = salt.utils.jinja.regex_replace
    jinja_env.filters['uuid'] = salt.utils.jinja.uuid_
    jinja_env.filters['min'] = salt.utils.jinja.lst_min
    jinja_env.filters['max'] = salt.utils.jinja.lst_max
    jinja_env.filters['avg'] = salt.utils.jinja.lst_avg
    jinja_env.filters['union'] = salt.utils.jinja.union
    jinja_env.filters['intersect'] = salt.utils.jinja.intersect
    jinja_env.filters['difference'] = salt.utils.jinja.difference
    jinja_env.filters['symmetric_difference'] = salt.utils.jinja.symmetric_difference
    jinja_env.filters['md5'] = salt.utils.hashutils.md5_digest
    jinja_env.filters['sha256'] = salt.utils.hashutils.sha256_digest
    jinja_env.filters['sha512'] = salt.utils.hashutils.sha512_digest
    jinja_env.filters['hmac'] = salt.utils.hashutils.hmac_signature
    jinja_env.filters['is_sorted'] = salt.utils.isorted
    jinja_env.filters['is_text_file'] = salt.utils.istextfile
    jinja_env.filters['is_empty_file'] = salt.utils.is_empty
    jinja_env.filters['is_binary_file'] = salt.utils.is_bin_file
    jinja_env.filters['file_hashsum'] = salt.utils.get_hash
    jinja_env.filters['is_hex'] = salt.utils.is_hex
    jinja_env.filters['path_join'] = salt.utils.path_join
    jinja_env.filters['dns_check'] = salt.utils.dns_check
    jinja_env.filters['list_files'] = salt.utils.list_files
    jinja_env.filters['which'] = salt.utils.which
    jinja_env.filters['random_str'] = salt.utils.rand_str
    jinja_env.filters['get_uid'] = salt.utils.get_uid
    jinja_env.filters['mysql_to_dict'] = salt.utils.mysql_to_dict
    jinja_env.filters['contains_whitespace'] = salt.utils.contains_whitespace
    jinja_env.filters['str_to_num'] = salt.utils.str_to_num
    jinja_env.filters['check_whitelist_blacklist'] = salt.utils.check_whitelist_blacklist
    jinja_env.filters['mac_str_to_bytes'] = salt.utils.mac_str_to_bytes
    jinja_env.filters['date_format'] = salt.utils.date_format
    jinja_env.filters['compare_dicts'] = salt.utils.compare_dicts
    jinja_env.filters['compare_lists'] = salt.utils.compare_lists
    jinja_env.filters['json_decode_list'] = salt.utils.decode_list
    jinja_env.filters['json_decode_dict'] = salt.utils.decode_dict
    jinja_env.filters['is_list'] = salt.utils.is_list
    jinja_env.filters['is_iter'] = salt.utils.is_iter
    jinja_env.filters['to_bytes'] = salt.utils.to_bytes
    jinja_env.filters['substring_in_list'] = salt.utils.substr_in_list
    jinja_env.filters['base64_encode'] = salt.utils.hashutils.base64_b64encode
    jinja_env.filters['base64_decode'] = salt.utils.hashutils.base64_b64decode
    jinja_env.filters['yaml_dquote'] = salt.utils.yamlencoding.yaml_dquote
    jinja_env.filters['yaml_squote'] = salt.utils.yamlencoding.yaml_squote
    jinja_env.filters['yaml_encode'] = salt.utils.yamlencoding.yaml_encode
    jinja_env.filters['gen_mac'] = salt.utils.gen_mac
    jinja_env.filters['is_ip'] = salt.utils.network.is_ip_filter  # check if valid IP address
    jinja_env.filters['is_ipv4'] = salt.utils.network.is_ipv4_filter  # check if valid IPv4 address
    jinja_env.filters['is_ipv6'] = salt.utils.network.is_ipv6_filter  # check if valid IPv6 address
    jinja_env.filters['ipaddr'] = salt.utils.network.ipaddr  # filter IP addresses
    jinja_env.filters['ipv4'] = salt.utils.network.ipv4  # filter IPv4-only addresses
    jinja_env.filters['ipv6'] = salt.utils.network.ipv6  # filter IPv6-only addresses
    jinja_env.filters['ip_host'] = salt.utils.network.ip_host  # return the network interface IP
    jinja_env.filters['network_hosts'] = salt.utils.network.network_hosts  # return the hosts within a network
    jinja_env.filters['network_size'] = salt.utils.network.network_size  # return the network size

    # globals
    jinja_env.globals['odict'] = OrderedDict
    jinja_env.globals['show_full_context'] = salt.utils.jinja.show_full_context

    jinja_env.tests['list'] = salt.utils.is_list

    decoded_context = {}
    for key, value in six.iteritems(context):
        if not isinstance(value, six.string_types):
            decoded_context[key] = value
            continue

        decoded_context[key] = salt.utils.locales.sdecode(value)

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
        log.debug("Jinja Error")
        log.debug("Exception: {0}".format(exc))
        log.debug("Out: {0}".format(out))
        log.debug("Line: {0}".format(line))
        log.debug("TmplStr: {0}".format(tmplstr))
        log.debug("TraceStr: {0}".format(tracestr))

        raise SaltRenderError('Jinja error: {0}{1}'.format(exc, out),
                              line,
                              tmplstr,
                              trace=tracestr)

    # Workaround a bug in Jinja that removes the final newline
    # (https://github.com/mitsuhiko/jinja2/issues/75)
    if newline:
        output += '\n'

    return output


# pylint: disable=3rd-party-module-not-gated
def render_mako_tmpl(tmplstr, context, tmplpath=None):
    import mako.exceptions
    from mako.template import Template
    from salt.utils.mako import SaltMakoTemplateLookup

    saltenv = context['saltenv']
    lookup = None
    if not saltenv:
        if tmplpath:
            # i.e., the template is from a file outside the state tree
            from mako.lookup import TemplateLookup
            lookup = TemplateLookup(directories=[os.path.dirname(tmplpath)])
    else:
        lookup = SaltMakoTemplateLookup(
                context['opts'],
                saltenv,
                pillar_rend=context.get('_pillar_rend', False))
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


def render_genshi_tmpl(tmplstr, context, tmplpath=None):
    '''
    Render a Genshi template. A method should be passed in as part of the
    context. If no method is passed in, xml is assumed. Valid methods are:

    .. code-block:

        - xml
        - xhtml
        - html
        - text
        - newtext
        - oldtext

    Note that the ``text`` method will call ``NewTextTemplate``. If ``oldtext``
    is desired, it must be called explicitly
    '''
    method = context.get('method', 'xml')
    if method == 'text' or method == 'newtext':
        from genshi.template import NewTextTemplate
        tmpl = NewTextTemplate(tmplstr)
    elif method == 'oldtext':
        from genshi.template import OldTextTemplate
        tmpl = OldTextTemplate(tmplstr)
    else:
        from genshi.template import MarkupTemplate
        tmpl = MarkupTemplate(tmplstr)

    return tmpl.generate(**context).render(method)


def render_cheetah_tmpl(tmplstr, context, tmplpath=None):
    '''
    Render a Cheetah template.
    '''
    from Cheetah.Template import Template
    return str(Template(tmplstr, searchList=[context]))
# pylint: enable=3rd-party-module-not-gated


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
    # File templates need these set as __var__
    if '__env__' not in kwargs and 'saltenv' in kwargs:
        setattr(mod, '__env__', kwargs['saltenv'])
        builtins = ['salt', 'grains', 'pillar', 'opts']
        for builtin in builtins:
            arg = '__{0}__'.format(builtin)
            setattr(mod, arg, kwargs[builtin])

    for kwarg in kwargs:
        setattr(mod, kwarg, kwargs[kwarg])

    try:
        data = mod.run()
        if string:
            return {'result': True,
                    'data': data}
        tgt = salt.utils.files.mkstemp()
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
GENSHI = wrap_tmpl_func(render_genshi_tmpl)
CHEETAH = wrap_tmpl_func(render_cheetah_tmpl)

TEMPLATE_REGISTRY = {
    'jinja': JINJA,
    'mako': MAKO,
    'py': py,
    'wempy': WEMPY,
    'genshi': GENSHI,
    'cheetah': CHEETAH,
}
