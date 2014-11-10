# -*- coding: utf-8 -*-

'''
Provide authentication using YubiKey

To get your YubiKey API key you will need to visit the website below.

https://upgrade.yubico.com/getapikey/

The resulting page will show the generated Client ID (aka AuthID or API ID)
and the generated API key (Secret Key). Make a note of both and use these
two values in your /etc/salt/master configuration.

  /etc/salt/master

  .. code-block:: yaml

    yubico_users:
      damian:
        id: 12345
        key: ABCDEFGHIJKLMNOPQRSTUVWXYZ


  .. code-block:: yaml

    external_auth:
      yubico:
        damian:
          - test.*


Please wait five to ten minutes after generating the key before testing so that
the API key will be updated on all the YubiCloud servers.

:depends:   - yubico-client Python module
'''

from __future__ import print_function

from __future__ import absolute_import
import logging

log = logging.getLogger(__name__)

try:
    from yubico_client import Yubico, yubico_exceptions
    HAS_YUBICO = True
except ImportError:
    HAS_YUBICO = False


def __get_yubico_users(username):
    '''
    Grab the YubiKey Client ID & Secret Key
    '''
    user = {}

    try:
        if __opts__['yubico_users'].get(username, None):
            (user['id'], user['key']) = list(__opts__['yubico_users'][username].values())
        else:
            return None
    except KeyError:
        return None

    return user


def auth(username, password):
    '''
    Authentcate against yubico server
    '''
    _cred = __get_yubico_users(username)

    client = Yubico(_cred['id'], _cred['key'])

    try:
        if client.verify(password):
            return True
        else:
            return False
    except yubico_exceptions.StatusCodeError as e:
        log.info('Unable to verify YubiKey `{0}`'.format(e))
        return False

    return False


if __name__ == '__main__':
    __opts__ = {'yubico_users': {'damian': {'id': '12345', 'key': 'ABC123'}}}

    if auth('damian', 'OPT'):
        print("Authenticated")
    else:
        print("Failed to authenticate")
