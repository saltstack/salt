"""
Template render systems
"""

import codecs
import importlib.machinery
import importlib.util
import logging
import os
import pathlib
import sys
import tempfile
import traceback

import jinja2
import jinja2.ext
import jinja2.sandbox

import salt.modules.match
import salt.utils.data
import salt.utils.dateutils
import salt.utils.files
import salt.utils.hashutils
import salt.utils.http
import salt.utils.jinja
import salt.utils.network
import salt.utils.platform
import salt.utils.stringutils
import salt.utils.yamlencoding
from salt import __path__ as saltpath
from salt.exceptions import CommandExecutionError, SaltInvocationError, SaltRenderError
from salt.loader.context import NamedLoaderContext
from salt.utils.decorators.jinja import JinjaFilter, JinjaGlobal, JinjaTest
from salt.utils.odict import OrderedDict
from salt.utils.versions import Version

log = logging.getLogger(__name__)


TEMPLATE_DIRNAME = os.path.join(saltpath[0], "templates")

# FIXME: also in salt/template.py
SLS_ENCODING = "utf-8"  # this one has no BOM.
SLS_ENCODER = codecs.getencoder(SLS_ENCODING)


class AliasedLoader:
    """
    Light wrapper around the LazyLoader to redirect 'cmd.run' calls to
    'cmd.shell', for easy use of shellisms during templating calls

    Dotted aliases ('cmd.run') must resolve to another dotted alias
    (e.g. 'cmd.shell')

    Non-dotted aliases ('cmd') must resolve to a dictionary of function
    aliases for that module (e.g. {'run': 'shell'})
    """

    def __init__(self, wrapped):
        self.wrapped = wrapped

    def __getitem__(self, name):
        return self.wrapped[name]

    def __getattr__(self, name):
        return getattr(self.wrapped, name)

    def __contains__(self, name):
        return name in self.wrapped


class AliasedModule:
    """
    Light wrapper around module objects returned by the LazyLoader's getattr
    for the purposes of `salt.cmd.run()` syntax in templates

    Allows for aliasing specific functions, such as `run` to `shell` for easy
    use of shellisms during templating calls
    """

    def __init__(self, wrapped, aliases):
        self.aliases = aliases
        self.wrapped = wrapped

    def __getattr__(self, name):
        return getattr(self.wrapped, name)


def generate_sls_context(tmplpath, sls):
    """
    Generate SLS/Template Context Items

    Return values:

    tplpath - full path to template on filesystem including filename
    tplfile - relative path to template -- relative to file roots
    tpldir - directory of the template relative to file roots. If none, "."
    tpldot - tpldir using dots instead of slashes, if none, ""
    slspath - directory containing current sls - (same as tpldir), if none, ""
    sls_path - slspath with underscores separating parts, if none, ""
    slsdotpath - slspath with dots separating parts, if none, ""
    slscolonpath- slspath with colons separating parts, if none, ""

    """

    sls_context = {}

    # Normalize SLS as path.
    slspath = sls.replace(".", "/")

    if tmplpath:
        # Normalize template path
        template = str(pathlib.Path(tmplpath).as_posix())

        # Determine proper template name without root
        if not sls:
            template = template.rsplit("/", 1)[-1]
        elif template.endswith(f"{slspath}.sls"):
            template = template[-(4 + len(slspath)) :]
        elif template.endswith(f"{slspath}/init.sls"):
            template = template[-(9 + len(slspath)) :]
        else:
            # Something went wrong
            log.warning("Failed to determine proper template path")

        slspath = template.rsplit("/", 1)[0] if "/" in template else ""

        sls_context.update(
            dict(
                tplpath=tmplpath,
                tplfile=template,
                tpldir=slspath if slspath else ".",
                tpldot=slspath.replace("/", "."),
            )
        )

    # Should this be normalized?
    sls_context.update(
        dict(
            slspath=slspath,
            slsdotpath=slspath.replace("/", "."),
            slscolonpath=slspath.replace("/", ":"),
            sls_path=slspath.replace("/", "_"),
        )
    )

    return sls_context


def wrap_tmpl_func(render_str):
    """
    Each template processing function below, ``render_*_tmpl``, is wrapped by
    ``render_tmpl`` before being inserted into the ``TEMPLATE_REGISTRY``.  Some
    actions are taken here that are common to all renderers.  Perhaps a
    standard decorator construct would have been more legible.

    :param function render_str: Template rendering function to be wrapped.
        Each function is responsible for rendering the source data for its
        repective template language.

    :returns function render_tmpl: The wrapper function
    """

    def render_tmpl(
        tmplsrc, from_str=False, to_str=False, context=None, tmplpath=None, **kws
    ):

        if context is None:
            context = {}

        # Alias cmd.run to cmd.shell to make python_shell=True the default for
        # templated calls
        if "salt" in kws:
            kws["salt"] = AliasedLoader(kws["salt"])

        # We want explicit context to overwrite the **kws
        kws.update(context)
        context = kws
        assert "opts" in context
        assert "saltenv" in context

        if "sls" in context:
            sls_context = generate_sls_context(tmplpath, context["sls"])
            context.update(sls_context)

        if isinstance(tmplsrc, str):
            if from_str:
                tmplstr = tmplsrc
            else:
                try:
                    if tmplpath is not None:
                        tmplsrc = os.path.join(tmplpath, tmplsrc)
                    with codecs.open(tmplsrc, "r", SLS_ENCODING) as _tmplsrc:
                        tmplstr = _tmplsrc.read()
                except (UnicodeDecodeError, ValueError, OSError) as exc:
                    if salt.utils.files.is_binary(tmplsrc):
                        # Template is a bin file, return the raw file
                        return dict(result=True, data=tmplsrc)
                    log.error(
                        "Exception occurred while reading file %s: %s",
                        tmplsrc,
                        exc,
                        exc_info_on_loglevel=logging.DEBUG,
                    )
                    raise
        else:  # assume tmplsrc is file-like.
            tmplstr = tmplsrc.read()
            tmplsrc.close()
        try:
            output = render_str(tmplstr, context, tmplpath)
            if salt.utils.platform.is_windows():
                newline = False
                if salt.utils.stringutils.to_unicode(
                    output, encoding=SLS_ENCODING
                ).endswith(("\n", os.linesep)):
                    newline = True
                # Write out with Windows newlines
                output = os.linesep.join(output.splitlines())
                if newline:
                    output += os.linesep

        except SaltRenderError as exc:
            log.exception("Rendering exception occurred")
            # return dict(result=False, data=str(exc))
            raise
        except Exception:  # pylint: disable=broad-except
            return dict(result=False, data=traceback.format_exc())
        else:
            if to_str:  # then render as string
                return dict(result=True, data=output)
            with tempfile.NamedTemporaryFile(
                "wb", delete=False, prefix=salt.utils.files.TEMPFILE_PREFIX
            ) as outf:
                outf.write(
                    salt.utils.stringutils.to_bytes(output, encoding=SLS_ENCODING)
                )
                # Note: If nothing is replaced or added by the rendering
                #       function, then the contents of the output file will
                #       be exactly the same as the input.
            return dict(result=True, data=outf.name)

    render_tmpl.render_str = render_str
    return render_tmpl


def _get_jinja_error_slug(tb_data):
    """
    Return the line number where the template error was found
    """
    try:
        return [
            x
            for x in tb_data
            if x[2] in ("top-level template code", "template", "<module>")
        ][-1]
    except IndexError:
        pass


def _get_jinja_error_message(tb_data):
    """
    Return an understandable message from jinja error output
    """
    try:
        line = _get_jinja_error_slug(tb_data)
        return "{0}({1}):\n{3}".format(*line)
    except IndexError:
        pass
    return None


def _get_jinja_error_line(tb_data):
    """
    Return the line number where the template error was found
    """
    try:
        return _get_jinja_error_slug(tb_data)[1]
    except IndexError:
        pass
    return None


def _get_jinja_error(trace, context=None):
    """
    Return the error line and error message output from
    a stacktrace.
    If we are in a macro, also output inside the message the
    exact location of the error in the macro
    """
    if not context:
        context = {}
    out = ""
    error = _get_jinja_error_slug(trace)
    line = _get_jinja_error_line(trace)
    msg = _get_jinja_error_message(trace)
    # if we failed on a nested macro, output a little more info
    # to help debugging
    # if sls is not found in context, add output only if we can
    # resolve the filename
    add_log = False
    template_path = None
    if "sls" not in context:
        if (error[0] != "<unknown>") and os.path.exists(error[0]):
            template_path = error[0]
            add_log = True
    else:
        # the offender error is not from the called sls
        filen = context["sls"].replace(".", "/")
        if not error[0].endswith(filen) and os.path.exists(error[0]):
            add_log = True
            template_path = error[0]
    # if we add a log, format explicitly the exception here
    # by telling to output the macro context after the macro
    # error log place at the beginning
    if add_log:
        if template_path:
            out = f"\n{msg.splitlines()[0]}\n"
            with salt.utils.files.fopen(template_path) as fp_:
                template_contents = salt.utils.stringutils.to_unicode(fp_.read())
            out += salt.utils.stringutils.get_context(
                template_contents, line, marker="    <======================"
            )
        else:
            out = f"\n{msg}\n"
        line = 0
    return line, out


def render_jinja_tmpl(tmplstr, context, tmplpath=None):
    """
    Render a Jinja template.

    :param str tmplstr: A string containing the source to be rendered.

    :param dict context: Any additional context data used by the renderer.

    :param str tmplpath: Base path from which ``tmplstr`` may load additional
        template files.

    :returns str: The string rendered by the template.
    """
    opts = context["opts"]
    saltenv = context["saltenv"]
    loader = None
    newline = False

    if tmplstr and not isinstance(tmplstr, str):
        # https://jinja.palletsprojects.com/en/2.11.x/api/#unicode
        tmplstr = tmplstr.decode(SLS_ENCODING)

    if tmplstr.endswith(os.linesep):
        newline = os.linesep
    elif tmplstr.endswith("\n"):
        newline = "\n"

    try:
        if not saltenv:
            if tmplpath:
                loader = jinja2.FileSystemLoader(os.path.dirname(tmplpath))
        else:
            from salt.loader.dunder import __file_client__

            loader = salt.utils.jinja.SaltCacheLoader(
                opts,
                saltenv,
                pillar_rend=context.get("_pillar_rend", False),
                _file_client=context.get("fileclient", __file_client__.value()),
            )

        env_args = {"extensions": [], "loader": loader}

        if hasattr(jinja2.ext, "with_"):
            env_args["extensions"].append("jinja2.ext.with_")
        if hasattr(jinja2.ext, "do"):
            env_args["extensions"].append("jinja2.ext.do")
        if hasattr(jinja2.ext, "loopcontrols"):
            env_args["extensions"].append("jinja2.ext.loopcontrols")
        env_args["extensions"].append(salt.utils.jinja.SerializerExtension)

        opt_jinja_env = opts.get("jinja_env", {})
        opt_jinja_sls_env = opts.get("jinja_sls_env", {})

        opt_jinja_env = opt_jinja_env if isinstance(opt_jinja_env, dict) else {}
        opt_jinja_sls_env = (
            opt_jinja_sls_env if isinstance(opt_jinja_sls_env, dict) else {}
        )

        # Pass through trim_blocks and lstrip_blocks Jinja parameters
        # trim_blocks removes newlines around Jinja blocks
        # lstrip_blocks strips tabs and spaces from the beginning of
        # line to the start of a block.
        if opts.get("jinja_trim_blocks", False):
            log.debug("Jinja2 trim_blocks is enabled")
            log.warning(
                "jinja_trim_blocks is deprecated and will be removed in a future release,"
                " please use jinja_env and/or jinja_sls_env instead"
            )
            opt_jinja_env["trim_blocks"] = True
            opt_jinja_sls_env["trim_blocks"] = True
        if opts.get("jinja_lstrip_blocks", False):
            log.debug("Jinja2 lstrip_blocks is enabled")
            log.warning(
                "jinja_lstrip_blocks is deprecated and will be removed in a future release,"
                " please use jinja_env and/or jinja_sls_env instead"
            )
            opt_jinja_env["lstrip_blocks"] = True
            opt_jinja_sls_env["lstrip_blocks"] = True

        def opt_jinja_env_helper(opts, optname):
            for k, v in opts.items():
                k = k.lower()
                if hasattr(jinja2.defaults, k.upper()):
                    log.debug(
                        "Jinja2 environment %s was set to %s by %s", k, v, optname
                    )
                    env_args[k] = v
                else:
                    log.warning("Jinja2 environment %s is not recognized", k)

        if "sls" in context and context["sls"] != "":
            opt_jinja_env_helper(opt_jinja_sls_env, "jinja_sls_env")
        else:
            opt_jinja_env_helper(opt_jinja_env, "jinja_env")

        if opts.get("allow_undefined", False):
            jinja_env = jinja2.sandbox.SandboxedEnvironment(**env_args)
        else:
            jinja_env = jinja2.sandbox.SandboxedEnvironment(
                undefined=jinja2.StrictUndefined, **env_args
            )

        indent_filter = jinja_env.filters.get("indent")
        jinja_env.tests.update(JinjaTest.salt_jinja_tests)
        jinja_env.filters.update(JinjaFilter.salt_jinja_filters)
        if salt.utils.jinja.JINJA_VERSION >= Version("2.11"):
            # Use the existing indent filter on Jinja versions where it's not broken
            jinja_env.filters["indent"] = indent_filter
        jinja_env.globals.update(JinjaGlobal.salt_jinja_globals)

        # globals
        jinja_env.globals["odict"] = OrderedDict
        jinja_env.globals["show_full_context"] = salt.utils.jinja.show_full_context

        jinja_env.tests["list"] = salt.utils.data.is_list

        decoded_context = {}
        for key, value in context.items():
            if not isinstance(value, str):
                if isinstance(value, NamedLoaderContext):
                    decoded_context[key] = value.value()
                else:
                    decoded_context[key] = value
                continue

            try:
                decoded_context[key] = salt.utils.stringutils.to_unicode(
                    value, encoding=SLS_ENCODING
                )
            except UnicodeDecodeError:
                log.debug(
                    "Failed to decode using default encoding (%s), trying system encoding",
                    SLS_ENCODING,
                )
                decoded_context[key] = salt.utils.data.decode(value)

        jinja_env.globals.update(decoded_context)
        try:
            template = jinja_env.from_string(tmplstr)
            output = template.render(**decoded_context)
        except jinja2.exceptions.UndefinedError as exc:
            trace = traceback.extract_tb(sys.exc_info()[2])
            line, out = _get_jinja_error(trace, context=decoded_context)
            if not line:
                tmplstr = ""
            raise SaltRenderError(f"Jinja variable {exc}{out}", line, tmplstr)
        except (
            jinja2.exceptions.TemplateRuntimeError,
            jinja2.exceptions.TemplateSyntaxError,
            jinja2.exceptions.SecurityError,
        ) as exc:
            trace = traceback.extract_tb(sys.exc_info()[2])
            line, out = _get_jinja_error(trace, context=decoded_context)
            if not line:
                tmplstr = ""
            raise SaltRenderError(f"Jinja syntax error: {exc}{out}", line, tmplstr)
        except (SaltInvocationError, CommandExecutionError) as exc:
            trace = traceback.extract_tb(sys.exc_info()[2])
            line, out = _get_jinja_error(trace, context=decoded_context)
            if not line:
                tmplstr = ""
            raise SaltRenderError(
                "Problem running salt function in Jinja template: {}{}".format(
                    exc, out
                ),
                line,
                tmplstr,
            )
        except Exception as exc:  # pylint: disable=broad-except
            tracestr = traceback.format_exc()
            trace = traceback.extract_tb(sys.exc_info()[2])
            line, out = _get_jinja_error(trace, context=decoded_context)
            if not line:
                tmplstr = ""
            else:
                tmplstr += f"\n{tracestr}"
            log.debug("Jinja Error")
            log.debug("Exception:", exc_info=True)
            log.debug("Out: %s", out)
            log.debug("Line: %s", line)
            log.debug("TmplStr: %s", tmplstr)
            log.debug("TraceStr: %s", tracestr)

            raise SaltRenderError(
                f"Jinja error: {exc}{out}", line, tmplstr, trace=tracestr
            )
    finally:
        if loader and isinstance(loader, salt.utils.jinja.SaltCacheLoader):
            loader.destroy()

    # Workaround a bug in Jinja that removes the final newline
    # (https://github.com/mitsuhiko/jinja2/issues/75)
    if newline:
        output += newline

    return output


# pylint: disable=3rd-party-module-not-gated
def render_mako_tmpl(tmplstr, context, tmplpath=None):
    """
    Render a Mako template.

    :param str tmplstr: A string containing the source to be rendered.

    :param dict context: Any additional context data used by the renderer.

    :param str tmplpath: Base path from which ``tmplstr`` may load additional
        template files.

    :returns str: The string rendered by the template.
    """
    import mako.exceptions  # pylint: disable=no-name-in-module
    from mako.template import Template  # pylint: disable=no-name-in-module

    from salt.utils.mako import SaltMakoTemplateLookup

    saltenv = context["saltenv"]
    lookup = None
    if not saltenv:
        if tmplpath:
            # i.e., the template is from a file outside the state tree
            from mako.lookup import TemplateLookup  # pylint: disable=no-name-in-module

            lookup = TemplateLookup(directories=[os.path.dirname(tmplpath)])
    else:
        lookup = SaltMakoTemplateLookup(
            context["opts"], saltenv, pillar_rend=context.get("_pillar_rend", False)
        )
    try:
        return Template(
            tmplstr,
            strict_undefined=True,
            uri=context["sls"].replace(".", "/") if "sls" in context else None,
            lookup=lookup,
        ).render(**context)
    except Exception:  # pylint: disable=broad-except
        raise SaltRenderError(mako.exceptions.text_error_template().render())
    finally:
        if lookup and isinstance(lookup, SaltMakoTemplateLookup):
            lookup.destroy()


def render_wempy_tmpl(tmplstr, context, tmplpath=None):
    """
    Render a Wempy template.

    :param str tmplstr: A string containing the source to be rendered.

    :param dict context: Any additional context data used by the renderer.

    :param str tmplpath: Unused.

    :returns str: The string rendered by the template.
    """
    from wemplate.wemplate import TemplateParser as Template

    return Template(tmplstr).render(**context)


def render_genshi_tmpl(tmplstr, context, tmplpath=None):
    """
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
    """
    method = context.get("method", "xml")
    if method == "text" or method == "newtext":
        from genshi.template import NewTextTemplate  # pylint: disable=no-name-in-module

        tmpl = NewTextTemplate(tmplstr)
    elif method == "oldtext":
        from genshi.template import OldTextTemplate  # pylint: disable=no-name-in-module

        tmpl = OldTextTemplate(tmplstr)
    else:
        from genshi.template import MarkupTemplate  # pylint: disable=no-name-in-module

        tmpl = MarkupTemplate(tmplstr)

    return tmpl.generate(**context).render(method)


def render_cheetah_tmpl(tmplstr, context, tmplpath=None):
    """
    Render a Cheetah template.
    """
    from Cheetah.Template import Template

    # Compile the template and render it into the class
    tclass = Template.compile(tmplstr)
    data = tclass(namespaces=[context])

    # Figure out which method to call based on the type of tmplstr
    if isinstance(tmplstr, str):
        # This should call .__unicode__()
        res = str(data)
    elif isinstance(tmplstr, bytes):
        # This should call .__str()
        res = str(data)
    else:
        raise SaltRenderError(
            "Unknown type {!s} for Cheetah template while trying to render.".format(
                type(tmplstr)
            )
        )

    # Now we can decode it to the correct encoding
    return salt.utils.data.decode(res)


# pylint: enable=3rd-party-module-not-gated


def py(sfn, string=False, **kwargs):  # pylint: disable=C0103
    """
    Render a template from a python source file

    Returns::

        {'result': bool,
         'data': <Error data or rendered file path>}
    """
    if not os.path.isfile(sfn):
        return {}

    base_fname = os.path.basename(sfn)
    name = base_fname.split(".")[0]

    loader = importlib.machinery.SourceFileLoader(name, sfn)
    spec = importlib.util.spec_from_file_location(name, sfn, loader=loader)
    if spec is None:
        raise ImportError()
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.modules[name] = mod

    # File templates need these set as __var__
    if "__env__" not in kwargs and "saltenv" in kwargs:
        setattr(mod, "__env__", kwargs["saltenv"])
        builtins = ["salt", "grains", "pillar", "opts"]
        for builtin in builtins:
            arg = f"__{builtin}__"
            setattr(mod, arg, kwargs[builtin])

    for kwarg in kwargs:
        setattr(mod, kwarg, kwargs[kwarg])

    try:
        data = mod.run()
        if string:
            return {"result": True, "data": data}
        tgt = salt.utils.files.mkstemp()
        with salt.utils.files.fopen(tgt, "w+") as target:
            target.write(salt.utils.stringutils.to_str(data))
        return {"result": True, "data": tgt}
    except Exception:  # pylint: disable=broad-except
        trb = traceback.format_exc()
        return {"result": False, "data": trb}


JINJA = wrap_tmpl_func(render_jinja_tmpl)
MAKO = wrap_tmpl_func(render_mako_tmpl)
WEMPY = wrap_tmpl_func(render_wempy_tmpl)
GENSHI = wrap_tmpl_func(render_genshi_tmpl)
CHEETAH = wrap_tmpl_func(render_cheetah_tmpl)

TEMPLATE_REGISTRY = {
    "jinja": JINJA,
    "mako": MAKO,
    "py": py,
    "wempy": WEMPY,
    "genshi": GENSHI,
    "cheetah": CHEETAH,
}
