# -*- coding: utf-8 -*-
'''
:maintainer:    SaltStack
:maturity:      new
:platform:      all

Functions to interact with Hashicorp Vault.

:configuration: The salt-master must be configured to allow peer-runner
    configuration, as well as configuration for the module.

    Add this segment to the master configuration file, or
    /etc/salt/master.d/vault.conf:

    .. code-block:: yaml

        vault:
            url: https://vault.service.domain:8200
            auth:
                method: token
                token: 11111111-2222-3333-4444-555555555555
            policies:
                - saltstack/minions
                - saltstack/minion/{minion}
                .. more policies

    url
        Url to your Vault installation. Required.

    auth
        Currently only token auth is supported. The token must be able to create
        tokens with the policies that should be assigned to minions. Required.

    policies
        Policies that are assigned to minions when requesting a token. These can
        either be static, eg saltstack/minions, or templated, eg
        ``saltstack/minion/{minion}``. ``{minion}`` is shorthand for grains[id].
        Grains are also available, for example like this:
        ``my-policies/{grains[os]}``

        If a template contains a grain which evaluates to a list, it will be
        expanded into multiple policies. For example, given the template
        ``saltstack/by-role/{grains[roles]}``, and a minion having these grains:

        .. code-block: yaml

            grains:
                roles:
                    - web
                    - database

        The minion will have the policies ``saltstack/by-role/web`` and
        ``saltstack/by-role/database``. Note however that list members which do
        not have simple string representations, such as dictionaries or objects,
        do not work and will throw an exception. Strings and numbers are
        examples of types which work well.

        Optional. If policies is not configured, ``saltstack/minions`` and
        ``saltstack/{minion}`` are used as defaults.


    Add this segment to the master configuration file, or
    /etc/salt/master.d/peer_run.conf:

    .. code-block:: yaml

        peer_run:
            .*:
                - vault.generate_token
'''
from __future__ import absolute_import
import logging

import salt.crypt
import salt.exceptions


log = logging.getLogger(__name__)


def read_secret(path, key=None):
    '''
    Return the value of key at path in vault, or entire secret

    Jinja Example:

    .. code-block:: jinja

            my-secret: {{ salt['vault'].read_secret('secret/my/secret', 'some-key') }}

    .. code-block:: jinja

            {% set supersecret = salt['vault'].read_secret('secret/my/secret') %}
            secrets:
                first: {{ supersecret.first }}
                second: {{ supersecret.second }}
    '''
    log.debug('Reading Vault secret for {0} at {1}'.format(__grains__['id'], path))
    try:
        url = 'v1/{0}'.format(path)
        response = __utils__['vault.make_request']('GET', url)
        if response.status_code != 200:
            response.raise_for_status()
        data = response.json()['data']

        if key is not None:
            return data[key]
        return data
    except Exception as e:
        log.error('Failed to read secret! {0}: {1}'.format(type(e).__name__, e))
        raise salt.exceptions.CommandExecutionError(e)


def write_secret(path, **kwargs):
    '''
    Set secret at the path in vault. The vault policy used must allow this.

    CLI Example:

    .. code-block:: bash
            salt '*' vault.write_secret "secret/my/secret" user="foo" password="bar"
    '''
    log.debug(
        'Writing vault secrets for {0} at {1}'.
        format(__grains__['id'], path)
        )
    data = dict([(x, y) for x, y in kwargs.items() if not x.startswith('__')])
    try:
        url = 'v1/{0}'.format(path)
        response = __utils__['vault.make_request']('POST', url, json=data)
        if response.status_code != 204:
            response.raise_for_status()
        return True
    except Exception as e:
        log.error('Failed to write secret! {0}: {1}'.format(type(e).__name__, e))
        raise salt.exceptions.CommandExecutionError(e)


def delete_secret(path):
    '''
    Delete secret at the path in vault. The vault policy used must allow this.

    CLI Example:

    .. code-block:: bash
            salt '*' vault.delete_secret "secret/my/secret"
    '''
    log.debug('Deleting vault secrets for {0} in {1}'
              .format(__grains__['id'], path))
    try:
        url = 'v1/{0}'.format(path)
        response = __utils__['vault.make_request']('DELETE', url)
        if response.status_code != 204:
            response.raise_for_status()
        return True
    except Exception as e:
        log.error('Failed to delete secret! {0}: {1}'.format(type(e).__name__, e))
        raise salt.exceptions.CommandExecutionError(e)


def list_secrets(path):
    '''
    List secret keys at the path in vault. The vault policy used must allow this.
    The path should end with a trailing slash.

    CLI Example:

    .. code-block:: bash
            salt '*' vault.list_secrets "secret/my/"
    '''
    log.debug('Listing vault secret keys for {0} in {1}'
              .format(__grains__['id'], path))
    try:
        url = 'v1/{0}'.format(path)
        response = __utils__['vault.make_request']('LIST', url)
        if response.status_code != 200:
            response.raise_for_status()
        return response.json()['data']
    except Exception as e:
        log.error('Failed to list secrets! {0}: {1}'.format(type(e).__name__, e))
        raise salt.exceptions.CommandExecutionError(e)
