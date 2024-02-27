"""
TextFSM
=======

.. versionadded:: 2018.3.0

Execution module that processes plain text and extracts data
using TextFSM templates. The output is presented in JSON serializable
data, and can be easily re-used in other modules, or directly
inside the renderer (Jinja, Mako, Genshi, etc.).

:depends:   - textfsm Python library

.. note::

    Install  ``textfsm`` library: ``pip install textfsm``.
"""

import logging
import os

from salt.utils.files import fopen

try:
    import textfsm

    HAS_TEXTFSM = True
except ImportError:
    HAS_TEXTFSM = False

try:
    from textfsm import clitable

    HAS_CLITABLE = True
except ImportError:
    HAS_CLITABLE = False

log = logging.getLogger(__name__)

__virtualname__ = "textfsm"
__proxyenabled__ = ["*"]


def __virtual__():
    """
    Only load this execution module if TextFSM is installed.
    """
    if HAS_TEXTFSM:
        return __virtualname__
    return (
        False,
        "The textfsm execution module failed to load: requires the textfsm library.",
    )


def _clitable_to_dict(objects, fsm_handler):
    """
    Converts TextFSM cli_table object to list of dictionaries.
    """
    objs = []
    log.debug("Cli Table: %s; FSM handler: %s", objects, fsm_handler)
    for row in objects:
        temp_dict = {}
        for index, element in enumerate(row):
            temp_dict[fsm_handler.header[index].lower()] = element
        objs.append(temp_dict)
    log.debug("Extraction result: %s", objs)
    return objs


def extract(template_path, raw_text=None, raw_text_file=None, saltenv="base"):
    r"""
    Extracts the data entities from the unstructured
    raw text sent as input and returns the data
    mapping, processing using the TextFSM template.

    template_path
        The path to the TextFSM template.
        This can be specified using the absolute path
        to the file, or using one of the following URL schemes:

        - ``salt://``, to fetch the template from the Salt fileserver.
        - ``http://`` or ``https://``
        - ``ftp://``
        - ``s3://``
        - ``swift://``

    raw_text: ``None``
        The unstructured text to be parsed.

    raw_text_file: ``None``
        Text file to read, having the raw text to be parsed using the TextFSM template.
        Supports the same URL schemes as the ``template_path`` argument.

    saltenv: ``base``
        Salt fileserver environment from which to retrieve the file.
        Ignored if ``template_path`` is not a ``salt://`` URL.

    CLI Example:

    .. code-block:: bash

        salt '*' textfsm.extract salt://textfsm/juniper_version_template raw_text_file=s3://junos_ver.txt
        salt '*' textfsm.extract http://some-server/textfsm/juniper_version_template raw_text='Hostname: router.abc ... snip ...'

    Jinja template example:

    .. code-block:: jinja

        {%- set raw_text = 'Hostname: router.abc ... snip ...' -%}
        {%- set textfsm_extract = salt.textfsm.extract('https://some-server/textfsm/juniper_version_template', raw_text) -%}

    Raw text example:

    .. code-block:: text

        Hostname: router.abc
        Model: mx960
        JUNOS Base OS boot [9.1S3.5]
        JUNOS Base OS Software Suite [9.1S3.5]
        JUNOS Kernel Software Suite [9.1S3.5]
        JUNOS Crypto Software Suite [9.1S3.5]
        JUNOS Packet Forwarding Engine Support (M/T Common) [9.1S3.5]
        JUNOS Packet Forwarding Engine Support (MX Common) [9.1S3.5]
        JUNOS Online Documentation [9.1S3.5]
        JUNOS Routing Software Suite [9.1S3.5]

    TextFSM Example:

    .. code-block:: text

        Value Chassis (\S+)
        Value Required Model (\S+)
        Value Boot (.*)
        Value Base (.*)
        Value Kernel (.*)
        Value Crypto (.*)
        Value Documentation (.*)
        Value Routing (.*)

        Start
        # Support multiple chassis systems.
          ^\S+:$$ -> Continue.Record
          ^${Chassis}:$$
          ^Model: ${Model}
          ^JUNOS Base OS boot \[${Boot}\]
          ^JUNOS Software Release \[${Base}\]
          ^JUNOS Base OS Software Suite \[${Base}\]
          ^JUNOS Kernel Software Suite \[${Kernel}\]
          ^JUNOS Crypto Software Suite \[${Crypto}\]
          ^JUNOS Online Documentation \[${Documentation}\]
          ^JUNOS Routing Software Suite \[${Routing}\]

    Output example:

    .. code-block:: json

        {
            "comment": "",
            "result": true,
            "out": [
                {
                    "kernel": "9.1S3.5",
                    "documentation": "9.1S3.5",
                    "boot": "9.1S3.5",
                    "crypto": "9.1S3.5",
                    "chassis": "",
                    "routing": "9.1S3.5",
                    "base": "9.1S3.5",
                    "model": "mx960"
                }
            ]
        }
    """
    ret = {"result": False, "comment": "", "out": None}
    log.debug(
        "Caching %s(saltenv: %s) using the Salt fileserver", template_path, saltenv
    )
    tpl_cached_path = __salt__["cp.cache_file"](template_path, saltenv=saltenv)
    if tpl_cached_path is False:
        ret["comment"] = "Unable to read the TextFSM template from {}".format(
            template_path
        )
        log.error(ret["comment"])
        return ret
    try:
        log.debug("Reading TextFSM template from cache path: %s", tpl_cached_path)
        # Disabling pylint W8470 to nto complain about fopen.
        # Unfortunately textFSM needs the file handle rather than the content...
        # pylint: disable=W8470
        tpl_file_handle = fopen(tpl_cached_path, "r")
        # pylint: disable=W8470
        log.debug(tpl_file_handle.read())
        tpl_file_handle.seek(0)  # move the object position back at the top of the file
        fsm_handler = textfsm.TextFSM(tpl_file_handle)
    except textfsm.TextFSMTemplateError as tfte:
        log.error("Unable to parse the TextFSM template", exc_info=True)
        ret["comment"] = (
            "Unable to parse the TextFSM template from {}: {}. Please check the logs.".format(
                template_path, tfte
            )
        )
        return ret
    if not raw_text and raw_text_file:
        log.debug("Trying to read the raw input from %s", raw_text_file)
        raw_text = __salt__["cp.get_file_str"](raw_text_file, saltenv=saltenv)
        if raw_text is False:
            ret["comment"] = (
                "Unable to read from {}. Please specify a valid input file or text.".format(
                    raw_text_file
                )
            )
            log.error(ret["comment"])
            return ret
    if not raw_text:
        ret["comment"] = "Please specify a valid input file or text."
        log.error(ret["comment"])
        return ret
    log.debug("Processing the raw text:\n%s", raw_text)
    objects = fsm_handler.ParseText(raw_text)
    ret["out"] = _clitable_to_dict(objects, fsm_handler)
    ret["result"] = True
    return ret


def index(
    command,
    platform=None,
    platform_grain_name=None,
    platform_column_name=None,
    output=None,
    output_file=None,
    textfsm_path=None,
    index_file=None,
    saltenv="base",
    include_empty=False,
    include_pat=None,
    exclude_pat=None,
):
    """
    Dynamically identify the template required to extract the
    information from the unstructured raw text.

    The output has the same structure as the ``extract`` execution
    function, the difference being that ``index`` is capable
    to identify what template to use, based on the platform
    details and the ``command``.

    command
        The command executed on the device, to get the output.

    platform
        The platform name, as defined in the TextFSM index file.

        .. note::
            For ease of use, it is recommended to define the TextFSM
            indexfile with values that can be matches using the grains.

    platform_grain_name
        The name of the grain used to identify the platform name
        in the TextFSM index file.

        .. note::
            This option can be also specified in the minion configuration
            file or pillar as ``textfsm_platform_grain``.

        .. note::
            This option is ignored when ``platform`` is specified.

    platform_column_name: ``Platform``
        The column name used to identify the platform,
        exactly as specified in the TextFSM index file.
        Default: ``Platform``.

        .. note::
            This is field is case sensitive, make sure
            to assign the correct value to this option,
            exactly as defined in the index file.

        .. note::
            This option can be also specified in the minion configuration
            file or pillar as ``textfsm_platform_column_name``.

    output
        The raw output from the device, to be parsed
        and extract the structured data.

    output_file
        The path to a file that contains the raw output from the device,
        used to extract the structured data.
        This option supports the usual Salt-specific schemes: ``file://``,
        ``salt://``, ``http://``, ``https://``, ``ftp://``, ``s3://``, ``swift://``.

    textfsm_path
        The path where the TextFSM templates can be found. This can be either
        absolute path on the server, either specified using the following URL
        schemes: ``file://``, ``salt://``, ``http://``, ``https://``, ``ftp://``,
        ``s3://``, ``swift://``.

        .. note::
            This needs to be a directory with a flat structure, having an
            index file (whose name can be specified using the ``index_file`` option)
            and a number of TextFSM templates.

        .. note::
            This option can be also specified in the minion configuration
            file or pillar as ``textfsm_path``.

    index_file: ``index``
        The name of the TextFSM index file, under the ``textfsm_path``. Default: ``index``.

        .. note::
            This option can be also specified in the minion configuration
            file or pillar as ``textfsm_index_file``.

    saltenv: ``base``
        Salt fileserver environment from which to retrieve the file.
        Ignored if ``textfsm_path`` is not a ``salt://`` URL.

    include_empty: ``False``
        Include empty files under the ``textfsm_path``.

    include_pat
        Glob or regex to narrow down the files cached from the given path.
        If matching with a regex, the regex must be prefixed with ``E@``,
        otherwise the expression will be interpreted as a glob.

    exclude_pat
        Glob or regex to exclude certain files from being cached from the given path.
        If matching with a regex, the regex must be prefixed with ``E@``,
        otherwise the expression will be interpreted as a glob.

        .. note::
            If used with ``include_pat``, files matching this pattern will be
            excluded from the subset of files defined by ``include_pat``.

    CLI Example:

    .. code-block:: bash

        salt '*' textfsm.index 'sh ver' platform=Juniper output_file=salt://textfsm/juniper_version_example textfsm_path=salt://textfsm/
        salt '*' textfsm.index 'sh ver' output_file=salt://textfsm/juniper_version_example textfsm_path=ftp://textfsm/ platform_column_name=Vendor
        salt '*' textfsm.index 'sh ver' output_file=salt://textfsm/juniper_version_example textfsm_path=https://some-server/textfsm/ platform_column_name=Vendor platform_grain_name=vendor

    TextFSM index file example:

    ``salt://textfsm/index``

    .. code-block:: text

        Template, Hostname, Vendor, Command
        juniper_version_template, .*, Juniper, sh[[ow]] ve[[rsion]]

    The usage can be simplified,
    by defining (some of) the following options: ``textfsm_platform_grain``,
    ``textfsm_path``, ``textfsm_platform_column_name``, or ``textfsm_index_file``,
    in the (proxy) minion configuration file or pillar.

    Configuration example:

    .. code-block:: yaml

        textfsm_platform_grain: vendor
        textfsm_path: salt://textfsm/
        textfsm_platform_column_name: Vendor

    And the CLI usage becomes as simple as:

    .. code-block:: bash

        salt '*' textfsm.index 'sh ver' output_file=salt://textfsm/juniper_version_example

    Usgae inside a Jinja template:

    .. code-block:: jinja

        {%- set command = 'sh ver' -%}
        {%- set output = salt.net.cli(command) -%}
        {%- set textfsm_extract = salt.textfsm.index(command, output=output) -%}
    """
    ret = {"out": None, "result": False, "comment": ""}
    if not HAS_CLITABLE:
        ret["comment"] = "TextFSM does not seem that has clitable embedded."
        log.error(ret["comment"])
        return ret
    if not platform:
        platform_grain_name = __opts__.get("textfsm_platform_grain") or __pillar__.get(
            "textfsm_platform_grain", platform_grain_name
        )
        if platform_grain_name:
            log.debug(
                "Using the %s grain to identify the platform name", platform_grain_name
            )
            platform = __grains__.get(platform_grain_name)
            if not platform:
                ret["comment"] = (
                    "Unable to identify the platform name using the {} grain.".format(
                        platform_grain_name
                    )
                )
                return ret
            log.info("Using platform: %s", platform)
        else:
            ret["comment"] = (
                "No platform specified, no platform grain identifier configured."
            )
            log.error(ret["comment"])
            return ret
    if not textfsm_path:
        log.debug(
            "No TextFSM templates path specified, trying to look into the opts and"
            " pillar"
        )
        textfsm_path = __opts__.get("textfsm_path") or __pillar__.get("textfsm_path")
        if not textfsm_path:
            ret["comment"] = (
                "No TextFSM templates path specified. Please configure in"
                " opts/pillar/function args."
            )
            log.error(ret["comment"])
            return ret
    log.debug(
        "Caching %s(saltenv: %s) using the Salt fileserver", textfsm_path, saltenv
    )
    textfsm_cachedir_ret = __salt__["cp.cache_dir"](
        textfsm_path,
        saltenv=saltenv,
        include_empty=include_empty,
        include_pat=include_pat,
        exclude_pat=exclude_pat,
    )
    log.debug("Cache fun return:\n%s", textfsm_cachedir_ret)
    if not textfsm_cachedir_ret:
        ret["comment"] = (
            "Unable to fetch from {}. Is the TextFSM path correctly specified?".format(
                textfsm_path
            )
        )
        log.error(ret["comment"])
        return ret
    textfsm_cachedir = os.path.dirname(textfsm_cachedir_ret[0])  # first item
    index_file = __opts__.get("textfsm_index_file") or __pillar__.get(
        "textfsm_index_file", "index"
    )
    index_file_path = os.path.join(textfsm_cachedir, index_file)
    log.debug("Using the cached index file: %s", index_file_path)
    log.debug("TextFSM templates cached under: %s", textfsm_cachedir)
    textfsm_obj = clitable.CliTable(index_file_path, textfsm_cachedir)
    attrs = {"Command": command}
    platform_column_name = __opts__.get(
        "textfsm_platform_column_name"
    ) or __pillar__.get("textfsm_platform_column_name", "Platform")
    log.info("Using the TextFSM platform idenfiticator: %s", platform_column_name)
    attrs[platform_column_name] = platform
    log.debug("Processing the TextFSM index file using the attributes: %s", attrs)
    if not output and output_file:
        log.debug("Processing the output from %s", output_file)
        output = __salt__["cp.get_file_str"](output_file, saltenv=saltenv)
        if output is False:
            ret["comment"] = (
                "Unable to read from {}. Please specify a valid file or text.".format(
                    output_file
                )
            )
            log.error(ret["comment"])
            return ret
    if not output:
        ret["comment"] = "Please specify a valid output text or file"
        log.error(ret["comment"])
        return ret
    log.debug("Processing the raw text:\n%s", output)
    try:
        # Parse output through template
        textfsm_obj.ParseCmd(output, attrs)
        ret["out"] = _clitable_to_dict(textfsm_obj, textfsm_obj)
        ret["result"] = True
    except clitable.CliTableError as cterr:
        log.error("Unable to proces the CliTable", exc_info=True)
        ret["comment"] = f"Unable to process the output: {cterr}"
    return ret
