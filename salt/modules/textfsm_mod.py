# -*- coding: utf-8 -*-
'''
TextFSM
=======

.. versionadded:: Oxygen

Execution module that processes plain text and extracts data
using TextFSM templates. The output is presented in JSON serializable
data, and can be easily re-used in other modules, or directly
inside the renderer (Jinja, Mako, Genshi, etc.).
'''
from __future__ import absolute_import

# Import python libs
import os
import logging

# Import third party modules
try:
    import textfsm
    HAS_TEXTFSM = True
except ImportError:
    HAS_TEXTFSM = False
try:
    import clitable
    HAS_CLITABLE = True
except ImportError:
    HAS_CLITABLE = False

# Import salt modules
import salt.utils

log = logging.getLogger(__name__)

__virtualname__ = 'textfsm'
__proxyenabled__ = ['*']


def __virtual__():
    return __virtualname__


def _clitable_to_dict(objects, fsm_handler):
    '''
    Converts TextFSM cli_table object to list of dictionaries.
    '''
    objs = []
    log.debug('Cli Table:')
    log.debug(objects)
    log.debug('FSM handler:')
    log.debug(fsm_handler)
    for row in objects:
        temp_dict = {}
        for index, element in enumerate(row):
            temp_dict[fsm_handler.header[index].lower()] = element
        objs.append(temp_dict)
    log.debug('Extraction result:')
    log.debug(objs)
    return objs


def extract(template_path, raw_text=None, raw_text_file=None, saltenv='base'):
    '''
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
        Salt fileserver envrionment from which to retrieve the file.
        Ignored if ``template_path`` is not a ``salt://`` URL.

    CLI Example:

    .. code-block:: bash

        salt '*' textfsm.extract salt://junos_ver.textfsm raw_text_file=s3://junos_ver.txt
        salt '*' textfsm.extract http://junos_ver.textfsm raw_text='Hostname: router.abc ... snip ...'

    .. code-block:: jinja

        {%- set raw_text = 'Hostname: router.abc ... snip ...' -%}
        {%- set textfsm_extract = salt.textfsm.extract('https://junos_ver.textfsm', raw_text) -%}

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
    '''
    ret = {
        'result': False,
        'comment': '',
        'out': None
    }
    tpl_cached_path = __salt__['cp.cache_file'](template_path, saltenv=saltenv)
    if tpl_cached_path is False:
        ret['comment'] = 'Unable to read the TextFSM template from {}'.format(template_path)
        log.error(ret['comment'])
        return ret
    try:
        log.debug('Reading TextFSM template from cache path: {}'.format(tpl_cached_path))
        tpl_file_handle = salt.utils.fopen(tpl_cached_path, 'r')
        fsm_handler = textfsm.TextFSM(tpl_file_handle)
    except textfsm.TextFSMTemplateError as tfte:
        log.error('Unable to parse the TextFSM template', exc_info=True)
        log.error(tpl_file_handle.read())
        ret['comment'] = 'Unable to parse the TextFSM template from {}. Please check the logs.'.format(template_path)
        return ret
    if not raw_text and raw_text_file:
        log.debug('Trying to read the raw input from {}'.format(raw_text_file))
        raw_text = __salt__['cp.get_file_str'](raw_text_file, saltenv=saltenv)
        log.debug('Raw text input read from file:')
        log.debug(raw_text)
        if raw_text is False:
            ret['comment'] = 'Unable to read from {}. Please specify a valid input file or text.'.format(raw_text_file)
            log.error(ret['comment'])
            return ret
    else:
        ret['comment'] = 'Please specify a valid input file or text.'
        log.error(ret['comment'])
        return ret
    objects = fsm_handler.ParseText(raw_text)
    ret['out'] = _clitable_to_dict(objects, fsm_handler)
    ret['result'] = True
    return ret


def index(command,
          platform,
          output=None,
          output_file=None,
          textfsm_path=None,
          index_file=None,
          saltenv='base',
          include_empty=False,
          include_pat=None,
          exclude_pat=None):
    ret = {
        'out': None,
        'result': False,
        'comment': ''
    }
    if not HAS_CLITABLE:
        ret['comment'] = 'TextFSM doesnt seem that has clitable embedded.'
        log.error(ret['comment'])
        return ret
    if not textfsm_path:
        log.debug('No TextFSM templates path specified, trying to look into the opts and pillar')
        textfsm_path = __opts__.get('textfsm_path') or __pillar__.get('textfsm_path')
        if not textfsm_path:
            ret['comment'] = 'No TextFSM templates path specified. Please configure in opts/pillar/function args.'
            log.error(ret['comment'])
            return ret
    log.debug('Caching {} using the Salt fileserver'.format(textfsm_path))
    textfsm_cachedir_ret = __salt__['cp.cache_dir'](textfsm_path,
                                                    saltenv=saltenv,
                                                    include_empty=include_empty,
                                                    include_pat=include_pat,
                                                    exclude_pat=exclude_pat)
    log.debug('Cache fun return:')
    log.debug(textfsm_cachedir_ret)
    if not textfsm_cachedir_ret:
        ret['comment'] = 'Unable to fetch from {}. Is the TextFSM path correctly specified?'.format(textfsm_path)
        log.error(ret['comment'])
        return ret
    textfsm_cachedir = os.path.dirname(textfsm_cachedir_ret[0])  # first item
    index_file = __opts__.get('textfsm_index', 'index')
    index_file_path = os.path.join(textfsm_cachedir, index_file)
    log.debug('Using the cached index file: {}'.format(index_file_path))
    log.debug('TextFSM templates cached under: {}'.format(textfsm_cachedir))
    textfsm_obj = clitable.CliTable(index_file_path, textfsm_cachedir)
    attrs = {
        'Command': command,
        'Platform': platform
    }
    log.debug('Command: {Command}, Platform: {Platform}'.format(**attrs))
    if not output and output_file:
        log.debug('Processing the output from {}'.format(output_file))
        output = __salt__['cp.get_file_str'](output_file, saltenv=saltenv)
        if output is False:
            ret['comment'] = 'Unable to read from {}. Please specify a valid file or text.'.format(output_file)
            log.error(ret['comment'])
            return ret
        log.debug('Raw text input read from file:')
        log.debug(output)
    else:
        ret['comment'] = 'Please specify a valid output text or file'
        log.error(ret['comment'])
        return ret
    try:
        # Parse output through template
        log.debug('Processing the output:')
        log.debug(output)
        textfsm_obj.ParseCmd(output, attrs)
        ret['out'] = _clitable_to_dict(textfsm_obj, textfsm_obj)
        ret['result'] = True
    except clitable.CliTableError as cterr:
        log.error('Unable to proces the CliTable', exc_info=True)
        ret['comment'] = 'Unable to process the output through the CliTable. Please see logs for more details.'
    return ret
