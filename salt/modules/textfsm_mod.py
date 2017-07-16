# -*- coding: utf-8 -*-
'''
TextFSM
========

.. versionadded:: Oxygen

Execution module that processes plain text and extracts data
using TextFSM templates. The output is presented in JSON serializable
data, and can be easily re-used in other modules, or directly
inside the renderer (Jinja, Mako, Genshi, etc.).
'''
from __future__ import absolute_import

# Import python libs
import logging
log = logging.getLogger(__name__)

# Import third party modules
import textfsm

# Import salt modules
import salt.utils

__virtualname__ = 'textfsm'
__proxyenabled__ = ['*']


def __virtual__():
    return __virtualname__


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

        salt '*' textfsm.extract salt://bgp.textfsm raw_text_file=s3://bgp.txt
        salt '*' textfsm.extract http://bgp.textfsm raw_text='Groups: 3 Peers: 3 Down peers: 0 ... snip ...'

    .. code-block:: jinja

        {%- set raw_text = 'Groups: 3 Peers: 3 Down peers: 0 ... snip ...' -%}
        {%- set textfsm_extract = salt.textfsm.extract('https://bgp.textfsm', raw_text) -%}

    Output example:

    .. code-block:: json

        {
            "comment": "",
            "result": true,
            "out": [
                {
                    "status": "",
                    "uptime": "6w3d17h",
                    "received_v6": "0",
                    "accepted_v6": "",
                    "remoteas": "65550",
                    "received_v4": "5",
                    "damped_v4": "1",
                    "active_v6": "0",
                    "remoteip": "10.247.68.182",
                    "active_v4": "4",
                    "accepted_v4": "",
                    "damped_v6": "0"
                },
                {
                    "status": "",
                    "uptime": "6w5d6h",
                    "received_v6": "8",
                    "accepted_v6": "",
                    "remoteas": "65550",
                    "received_v4": "0",
                    "damped_v4": "0",
                    "active_v6": "7",
                    "remoteip": "10.254.166.246",
                    "active_v4": "0",
                    "accepted_v4": "",
                    "damped_v6": "1"
                },
                {
                    "status": "",
                    "uptime": "9w5d6h",
                    "received_v6": "0",
                    "accepted_v6": "",
                    "remoteas": "65551",
                    "received_v4": "3",
                    "damped_v4": "0",
                    "active_v6": "0",
                    "remoteip": "192.0.2.100",
                    "active_v4": "2",
                    "accepted_v4": "",
                    "damped_v6": "0"
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
    textfsm_data = []
    for obj in objects:
        index = 0
        entry = {}
        for entry_value in obj:
            entry[fsm_handler.header[index].lower()] = entry_value
            index += 1
        textfsm_data.append(entry)
    ret.update({
        'result': True,
        'out': textfsm_data
    })
    return ret
