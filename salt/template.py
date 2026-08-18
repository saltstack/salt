"""
Manage basic template commands
"""

import codecs
import io
import logging
import os
import time

import salt.utils.data
import salt.utils.files
import salt.utils.sanitizers
import salt.utils.stringio
import salt.utils.versions

log = logging.getLogger(__name__)


# FIXME: we should make the default encoding of a .sls file a configurable
#        option in the config, and default it to 'utf-8'.
#
SLS_ENCODING = "utf-8"  # this one has no BOM.
SLS_ENCODER = codecs.getencoder(SLS_ENCODING)


def compile_template(
    template,
    renderers,
    default,
    blacklist,
    whitelist,
    saltenv="base",
    sls="",
    input_data="",
    context=None,
    **kwargs,
):
    """
    Take the path to a template and return the high data structure
    derived from the template.

    Helpers:

    :param mask_value:
        Mask value for debugging purposes (prevent sensitive information etc)
        example: "mask_value="pass*". All "passwd", "password", "pass" will
        be masked (as text).
    """

    # if any error occurs, we return an empty dictionary
    ret = {}

    log.debug("compile template: %s", template)

    if "env" in kwargs:
        # "env" is not supported; Use "saltenv".
        kwargs.pop("env")

    if template != ":string:":
        # Template was specified incorrectly
        if not isinstance(template, str):
            log.error("Template was specified incorrectly: %s", template)
            return ret
        # Template does not exist
        if not os.path.isfile(template):
            log.error("Template does not exist: %s", template)
            return ret
        # Template is an empty file
        if salt.utils.files.is_empty(template):
            log.debug("Template is an empty file: %s", template)
            return ret

        with codecs.open(template, encoding=SLS_ENCODING) as ifile:
            # data input to the first render function in the pipe
            input_data = ifile.read()
            if not input_data.strip():
                # Template is nothing but whitespace
                log.error("Template is nothing but whitespace: %s", template)
                return ret

    # Get the list of render funcs in the render pipe line.
    render_pipe = template_shebang(
        template, renderers, default, blacklist, whitelist, input_data
    )

    windows_newline = "\r\n" in input_data

    input_data = io.StringIO(input_data)
    for render, argline in render_pipe:
        if salt.utils.stringio.is_readable(input_data):
            input_data.seek(0)  # pylint: disable=no-member
        render_kwargs = dict(renderers=renderers, tmplpath=template)
        if context:
            render_kwargs["context"] = context
        render_kwargs.update(kwargs)
        if argline:
            render_kwargs["argline"] = argline
        start = time.time()
        ret = render(input_data, saltenv, sls, **render_kwargs)
        log.profile(
            "Time (in seconds) to render '%s' using '%s' renderer: %s",
            template,
            render.__module__.split(".")[-1],
            time.time() - start,
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
                    "Rendered data from file: %s:\n%s",
                    template,
                    salt.utils.sanitizers.mask_args_value(
                        salt.utils.data.decode(ret.read()), kwargs.get("mask_value")
                    ),
                )  # pylint: disable=no-member
                ret.seek(0)  # pylint: disable=no-member

    # Preserve newlines from original template
    if windows_newline:
        if salt.utils.stringio.is_readable(ret):
            is_stringio = True
            contents = ret.read()
        else:
            is_stringio = False
            contents = ret

        if isinstance(contents, str):
            if "\r\n" not in contents:
                contents = contents.replace("\n", "\r\n")
                ret = io.StringIO(contents) if is_stringio else contents
            else:
                if is_stringio:
                    ret.seek(0)
    return ret


def compile_template_str(template, renderers, default, blacklist, whitelist):
    """
    Take template as a string and return the high data structure
    derived from the template.
    """
    fn_ = salt.utils.files.mkstemp()
    with salt.utils.files.fopen(fn_, "wb") as ofile:
        ofile.write(SLS_ENCODER(template)[0])
    ret = compile_template(fn_, renderers, default, blacklist, whitelist)
    os.unlink(fn_)
    return ret


def template_shebang(template, renderers, default, blacklist, whitelist, input_data):
    """
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

    """
    line = ""
    # Open up the first line of the sls template
    if template == ":string:":
        line = input_data.split()[0]
    else:
        with salt.utils.files.fopen(template, "r") as ifile:
            line = salt.utils.stringutils.to_unicode(ifile.readline())

    # Check if it starts with a shebang and not a path
    if line.startswith("#!") and not line.startswith("#!/"):
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

for comb in (
    "yaml_jinja",
    "yaml_mako",
    "yaml_wempy",
    "json_jinja",
    "json_mako",
    "json_wempy",
    "yamlex_jinja",
    "yamlexyamlex_mako",
    "yamlexyamlex_wempy",
):

    fmt, tmpl = comb.split("_")
    OLD_STYLE_RENDERERS[comb] = f"{tmpl}|{fmt}"


def check_render_pipe_str(pipestr, renderers, blacklist, whitelist):
    """
    Check that all renderers specified in the pipe string are available.
    If so, return the list of render functions in the pipe as
    (render_func, arg_str) tuples; otherwise return [].
    """
    if pipestr is None:
        return []
    parts = [r.strip() for r in pipestr.split("|")]
    # Note: currently, | is not allowed anywhere in the shebang line except
    #       as pipes between renderers.

    results = []
    try:
        if parts[0] == pipestr and pipestr in OLD_STYLE_RENDERERS:
            parts = OLD_STYLE_RENDERERS[pipestr].split("|")
        for part in parts:
            name, argline = (part + " ").split(" ", 1)
            if whitelist and name not in whitelist or blacklist and name in blacklist:
                log.warning(
                    'The renderer "%s" is disallowed by configuration and '
                    "will be skipped.",
                    name,
                )
                continue
            results.append((renderers[name], argline.strip()))
        return results
    except KeyError:
        log.error('The renderer "%s" is not available', pipestr)
        return []
