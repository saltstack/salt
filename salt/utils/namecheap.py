# -*- coding: utf-8 -*-
'''
 Namecheap Management library of common functions used by
 all the namecheap execution modules

 Installation Prerequisites
 --------------------------

 - This module uses the following python libraries to communicate to
   the namecheap API:

        * ``requests``
        .. code-block:: bash

            pip install requests

'''

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function
import logging
import xml.dom.minidom

# Import Salt libs
import salt.loader

from salt.ext import six

# Import third party libs
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# Get logging started
log = logging.getLogger(__name__)

__salt__ = None


def __virtual__():
    if not HAS_REQUESTS:
        return False, 'Missing dependency: \'requests\'. The namecheap utils module ' \
                      'cannot be loaded. '
    global __salt__
    if not __salt__:
        __salt__ = salt.loader.minion_mods(__opts__)
    return True


def post_request(opts):
    namecheap_url = __salt__['config.option']('namecheap.url')
    return _handle_request(requests.post(namecheap_url, data=opts, timeout=45))


def get_request(opts):
    namecheap_url = __salt__['config.option']('namecheap.url')
    return _handle_request(requests.get(namecheap_url, params=opts, timeout=45))


def _handle_request(r):
    r.close()

    if r.status_code > 299:
        log.error(six.text_type(r))
        raise Exception(six.text_type(r))

    response_xml = xml.dom.minidom.parseString(r.text)
    apiresponse = response_xml.getElementsByTagName("ApiResponse")[0]

    if apiresponse.getAttribute('Status') == "ERROR":
        data = []
        errors = apiresponse.getElementsByTagName("Errors")[0]
        for e in errors.getElementsByTagName("Error"):
            data.append(e.firstChild.data)
        error = ''.join(data)
        log.info(apiresponse)
        log.error(error)
        raise Exception(error)

    return response_xml


def xml_to_dict(xml):
    if xml.nodeType == xml.CDATA_SECTION_NODE:
        return xml.data
    result = atts_to_dict(xml)
    if len([n for n in xml.childNodes if n.nodeType != xml.TEXT_NODE]) == 0:
        if len(result) > 0:
            if xml.firstChild is not None and len(xml.firstChild.data) > 0:
                result['data'] = xml.firstChild.data
        elif xml.firstChild is not None and len(xml.firstChild.data) > 0:
            return xml.firstChild.data
        else:
            return None
    elif xml.childNodes.length == 1 and \
         xml.childNodes[0].nodeType == xml.CDATA_SECTION_NODE:
        return xml.childNodes[0].data
    else:
        for n in xml.childNodes:
            if n.nodeType == xml.CDATA_SECTION_NODE:

                if xml.tagName.lower() in result:
                    val = result[xml.tagName.lower()]
                    if not isinstance(val, list):
                        temp = [val]
                        val = temp
                    val.append(n.data)
                    result[xml.tagName.lower()] = val
                else:
                    result[xml.tagName.lower()] = n.data

            elif n.nodeType != xml.TEXT_NODE:

                if n.tagName.lower() in result:
                    val = result[n.tagName.lower()]

                    if not isinstance(val, list):
                        temp = [val]
                        val = temp
                    val.append(xml_to_dict(n))
                    result[n.tagName.lower()] = val
                else:
                    result[n.tagName.lower()] = xml_to_dict(n)
    return result


def atts_to_dict(xml):
    result = {}
    if xml.attributes is not None:
        for key, value in xml.attributes.items():
            result[key.lower()] = string_to_value(value)
    return result


def string_to_value(value):
    temp = value.lower()
    result = None
    if temp == "true":
        result = True
    elif temp == "false":
        result = False
    else:
        try:
            result = int(value)
        except ValueError:
            try:
                result = float(value)
            except ValueError:
                result = value

    return result


def get_opts(command):
    opts = {}
    opts['ApiUser'] = __salt__['config.option']('namecheap.name')
    opts['UserName'] = __salt__['config.option']('namecheap.user')
    opts['ApiKey'] = __salt__['config.option']('namecheap.key')
    opts['ClientIp'] = __salt__['config.option']('namecheap.client_ip')
    opts['Command'] = command
    return opts
