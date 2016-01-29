# -*- coding: utf-8 -*-
'''
Use the :doc:`Salt Event System </topics/event/index>` to fire events from the
master to the minion and vice-versa.
'''
from __future__ import absolute_import
# Import Python libs
import collections
import logging
import os
import sys
import traceback

# Import salt libs
import salt.crypt
import salt.utils.event
import salt.payload
import salt.transport
import salt.ext.six as six

__proxyenabled__ = ['*']
log = logging.getLogger(__name__)


def _dict_subset(keys, master_dict):
    '''
    Return a dictionary of only the subset of keys/values specified in keys
    '''
    return dict([(k, v) for k, v in six.iteritems(master_dict) if k in keys])


def fire_master(data, tag, preload=None):
    '''
    Fire an event off up to the master server

    CLI Example:

    .. code-block:: bash

        salt '*' event.fire_master '{"data":"my event data"}' 'tag'
    '''
    if __opts__.get('local', None):
        #  We can't send an event if we're in masterless mode
        log.warning('Local mode detected. Event with tag {0} will NOT be sent.'.format(tag))
        return False
    if __opts__['transport'] == 'raet':
        channel = salt.transport.Channel.factory(__opts__)
        load = {'id': __opts__['id'],
                'tag': tag,
                'data': data,
                'cmd': '_minion_event'}
        try:
            channel.send(load)
        except Exception:
            pass
        return True

    if preload or __opts__.get('__cli') == 'salt-call':
        # If preload is specified, we must send a raw event (this is
        # slower because it has to independently authenticate)
        if 'master_uri' not in __opts__:
            __opts__['master_uri'] = 'tcp://{ip}:{port}'.format(
                    ip=salt.utils.ip_bracket(__opts__['interface']),
                    port=__opts__.get('ret_port', '4506')  # TODO, no fallback
                    )
        auth = salt.crypt.SAuth(__opts__)
        load = {'id': __opts__['id'],
                'tag': tag,
                'data': data,
                'tok': auth.gen_token('salt'),
                'cmd': '_minion_event'}

        if isinstance(preload, dict):
            load.update(preload)

        channel = salt.transport.Channel.factory(__opts__)
        try:
            channel.send(load)
        except Exception:
            pass
        return True
    else:
        # Usually, we can send the event via the minion, which is faster
        # because it is already authenticated
        try:
            return salt.utils.event.MinionEvent(__opts__, listen=False).fire_event(
                {'data': data, 'tag': tag, 'events': None, 'pretag': None}, 'fire_master')
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            log.debug(lines)
            return False


def fire(data, tag):
    '''
    Fire an event on the local minion event bus. Data must be formed as a dict.

    CLI Example:

    .. code-block:: bash

        salt '*' event.fire '{"data":"my event data"}' 'tag'
    '''
    try:
        event = salt.utils.event.get_event('minion',  # was __opts__['id']
                                           sock_dir=__opts__['sock_dir'],
                                           transport=__opts__['transport'],
                                           opts=__opts__,
                                           listen=False)

        return event.fire_event(data, tag)
    except Exception:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        log.debug(lines)
        return False


def send(tag,
        data=None,
        preload=None,
        with_env=False,
        with_grains=False,
        with_pillar=False,
        **kwargs):
    '''
    Send an event to the Salt Master

    .. versionadded:: 2014.7.0

    :param tag: A tag to give the event.
        Use slashes to create a namespace for related events. E.g.,
        ``myco/build/buildserver1/start``, ``myco/build/buildserver1/success``,
        ``myco/build/buildserver1/failure``.

    :param data: A dictionary of data to send in the event.
        This is free-form. Send any data points that are needed for whoever is
        consuming the event. Arguments on the CLI are interpreted as YAML so
        complex data structures are possible.

    :param with_env: Include environment variables from the current shell
        environment in the event data as ``environ``.. This is a short-hand for
        working with systems that seed the environment with relevant data such
        as Jenkins.
    :type with_env: Specify ``True`` to include all environment variables, or
        specify a list of strings of variable names to include.

    :param with_grains: Include grains from the current minion in the event
        data as ``grains``.
    :type with_grains: Specify ``True`` to include all grains, or specify a
        list of strings of grain names to include.

    :param with_pillar: Include Pillar values from the current minion in the
        event data as ``pillar``. Remember Pillar data is often sensitive data
        so be careful. This is useful for passing ephemeral Pillar values
        through an event. Such as passing the ``pillar={}`` kwarg in
        :py:func:`state.sls <salt.modules.state.sls>` from the Master, through
        an event on the Minion, then back to the Master.
    :type with_pillar: Specify ``True`` to include all Pillar values, or
        specify a list of strings of Pillar keys to include. It is a
        best-practice to only specify a relevant subset of Pillar data.

    :param kwargs: Any additional keyword arguments passed to this function
        will be interpreted as key-value pairs and included in the event data.
        This provides a convenient alternative to YAML for simple values.

    CLI Example:

    .. code-block:: bash

        salt-call event.send myco/mytag foo=Foo bar=Bar
        salt-call event.send 'myco/mytag' '{foo: Foo, bar: Bar}'

    A convenient way to allow Jenkins to execute ``salt-call`` is via sudo. The
    following rule in sudoers will allow the ``jenkins`` user to run only the
    following command.

    ``/etc/sudoers`` (allow preserving the environment):

    .. code-block:: text

        jenkins ALL=(ALL) NOPASSWD:SETENV: /usr/bin/salt-call event.send*

    Call Jenkins via sudo (preserve the environment):

    .. code-block:: bash

        sudo -E salt-call event.send myco/jenkins/build/success with_env=[BUILD_ID, BUILD_URL, GIT_BRANCH, GIT_COMMIT]

    '''
    data_dict = {}

    if with_env:
        if isinstance(with_env, list):
            data_dict['environ'] = _dict_subset(with_env, dict(os.environ))
        else:
            data_dict['environ'] = dict(os.environ)

    if with_grains:
        if isinstance(with_grains, list):
            data_dict['grains'] = _dict_subset(with_grains, __grains__)
        else:
            data_dict['grains'] = __grains__

    if with_pillar:
        if isinstance(with_pillar, list):
            data_dict['pillar'] = _dict_subset(with_pillar, __pillar__)
        else:
            data_dict['pillar'] = __pillar__

    if kwargs:
        data_dict.update(kwargs)

    # Allow values in the ``data`` arg to override any of the above values.
    if isinstance(data, collections.Mapping):
        data_dict.update(data)

    return fire_master(data_dict, tag, preload=preload)
