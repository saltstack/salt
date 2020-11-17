'''
Execution module for Restconf Proxy minions

:codeauthor: Jamie (Bear) Murphy <jamiemurphyit@gmail.com>
:maturity:   new
:platform:   any

'''
from __future__ import absolute_import

import six  # noqa: F401
import salt.utils  # noqa: F401

__proxyenabled__ = ["restconf"]
__virtualname__ = 'restconf'


def __virtual__():
    if __opts__.get("proxy", {}).get("proxytype") != __virtualname__:   # noqa: F821
        return False, "Proxytype does not match: {0}".format(__virtualname__)
    return True


def info():
    '''
        Should return some quick state info of the restconf device?
    '''
    return "Hello i am a restconf module"


def get_data(uri):
    return __proxy__['restconf.request'](uri)  # noqa: F821


def set_data(uri, method, dict_payload):
    return __proxy__['restconf.request'](uri, method, dict_payload)  # noqa: F821
