# -*- coding: utf-8 -*-
'''
Return salt data to Nagios

The following fields can be set in the minion conf file::

    nagios.url (required)
    nagios.token (required)
    nagios.service (optional)
    nagios.check_type (optional)

Alternative configuration values can be used by prefacing the configuration.
Any values not found in the alternative configuration will be pulled from
the default location::

    nagios.url
    nagios.token
    nagios.service

Nagios settings may also be configured as::

    nagios:
        url: http://localhost/nrdp
        token: r4nd0mt0k3n
        service: service-check

    alternative.nagios:
        url: http://localhost/nrdp
        token: r4nd0mt0k3n
        service: another-service-check

  To use the Nagios returner, append '--return nagios' to the salt command. ex:

  .. code-block:: bash

    salt '*' test.ping --return nagios

  To use the alternative configuration, append '--return_config alternative' to the salt command. ex:

    salt '*' test.ping --return nagios --return_config alternative

To override individual configuration items, append --return_kwargs '{"key:": "value"}' to the salt command.

.. versionadded:: 2016.3.0

.. code-block:: bash

    salt '*' test.ping --return nagios --return_kwargs '{"service": "service-name"}'

'''
from __future__ import absolute_import

# Import python libs
import cgi
import logging

import salt.returners
# pylint: disable=import-error,no-name-in-module,redefined-builtin
import salt.ext.six.moves.http_client
# pylint: enable=import-error,no-name-in-module,redefined-builtin

log = logging.getLogger(__name__)

__virtualname__ = 'nagios_nrdp'


def _get_options(ret=None):
    '''
    Get the requests options from salt.
    '''
    attrs = {'url': 'url',
             'token': 'token',
             'service': 'service',
             'checktype': 'checktype',
             }

    _options = salt.returners.get_returner_options(__virtualname__,
                                                   ret,
                                                   attrs,
                                                   __salt__=__salt__,
                                                   __opts__=__opts__)

    log.debug('attrs {0}'.format(attrs))
    if 'checktype' not in _options or _options['checktype'] == '':
        # default to passive check type
        _options['checktype'] = '1'

    if _options['checktype'] == 'active':
        _options['checktype'] = '0'

    if _options['checktype'] == 'passive':
        _options['checktype'] = '1'

    # checktype should be a string
    _options['checktype'] = str(_options['checktype'])

    return _options


def _prepare_xml(options=None, state=None):
    '''
    Get the requests options from salt.
    '''

    if state:
        _state = '0'
    else:
        _state = '2'

    xml = "<?xml version='1.0'?>\n<checkresults>\n"

    # No service defined then we set the status of the hostname
    if 'service' in options and options['service'] != '':
        xml += "<checkresult type='service' checktype='"+str(options['checktype'])+"'>"
        xml += "<hostname>"+cgi.escape(options['hostname'], True)+"</hostname>"
        xml += "<servicename>"+cgi.escape(options['service'], True)+"</servicename>"
    else:
        xml += "<checkresult type='host' checktype='"+str(options['checktype'])+"'>"
        xml += "<hostname>"+cgi.escape(options['hostname'], True)+"</hostname>"

    xml += "<state>"+_state+"</state>"

    if 'output' in options:
        xml += "<output>"+cgi.escape(options['output'], True)+"</output>"

    xml += "</checkresult>"

    xml += "\n</checkresults>"

    return xml


def _getText(nodelist):
    '''
    Simple function to return value from XML
    '''
    rc = []
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            rc.append(node.data)
    return ''.join(rc)


def _post_data(options=None, xml=None):
    '''
    Post data to Nagios NRDP
    '''
    params = {'token': options['token'].strip(), 'cmd': 'submitcheck', 'XMLDATA': xml}

    res = salt.utils.http.query(
        url=options['url'],
        method='POST',
        params=params,
        data='',
        decode=True,
        status=True,
        header_dict={},
        opts=__opts__,
    )

    if res.get('status', None) == salt.ext.six.moves.http_client.OK:
        if res.get('dict', None) and isinstance(res['dict'], list):
            _content = res['dict'][0]
            if _content.get('status', None):
                return True
            else:
                return False
        else:
            log.error('No content returned from Nagios NRDP.')
            return False
    else:
        log.error('Error returned from Nagios NRDP.  Status code: {0}.'.format(res.status_code))
        return False


def __virtual__():
    '''
    Return virtualname
    '''
    return __virtualname__


def returner(ret):
    '''
    Send a message to Nagios with the data
    '''

    _options = _get_options(ret)
    log.debug('_options {0}'.format(_options))
    _options['hostname'] = ret.get('id')

    if 'url' not in _options or _options['url'] == '':
        log.error('nagios_nrdp.url not defined in salt config')
        return

    if 'token' not in _options or _options['token'] == '':
        log.error('nagios_nrdp.token not defined in salt config')
        return

    xml = _prepare_xml(options=_options, state=ret['return'])
    res = _post_data(options=_options, xml=xml)

    return res
