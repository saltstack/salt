# -*- coding: utf-8 -*-
'''
Configuration management using Augeas
=====================================

.. versionadded:: 0.17.0

This state requires the ``augeas`` Python module.

.. _Augeas: http://augeas.net/

Augeas_ can be used to manage configuration files.

.. warning::

    Minimal installations of Debian and Ubuntu have been seen to have packaging
    bugs with python-augeas, causing the augeas module to fail to import. If
    the minion has the augeas module installed, and the state fails with a
    comment saying that the state is unavailable, first restart the salt-minion
    service. If the problem persists past that, the following command can be
    run from the master to determine what is causing the import to fail:

    .. code-block:: bash

        salt minion-id cmd.run 'python -c "from augeas import Augeas"'

    For affected Debian/Ubuntu hosts, installing ``libpython2.7`` has been
    known to resolve the issue.

'''

# Import python libs
import re
import os.path
import difflib


def __virtual__():
    return 'augeas' if 'augeas.execute' in __salt__ else False


def change(name, context=None, changes=None, lens=None, **kwargs):
    '''
    .. versionadded:: 2014.7.0

    This state replaces :py:func:`~salt.states.augeas.setvalue`.

    Issue changes to Augeas, optionally for a specific context, with a
    specific lens.

    name
        State name

    context
        The context to use. Set this to a file path, prefixed by ``/files``, to
        avoid redundancy, e.g.:

        .. code-block:: yaml

            redis-conf:
              augeas.change:
                - context: /files/etc/redis/redis.conf
                - changes:
                  - set bind 0.0.0.0
                  - set maxmemory 1G

    changes
        List of changes that are issued to Augeas. Available commands are
        ``set``, ``mv``/``move``, ``ins``/``insert``, and ``rm``/``remove``.

    lens
        The lens to use, needs to be suffixed with `.lns`, e.g.: `Nginx.lns`. See
        the `list of stock lenses <http://augeas.net/stock_lenses.html>`_
        shipped with Augeas.


    Usage examples:

    Set the ``bind`` parameter in ``/etc/redis/redis.conf``:

    .. code-block:: yaml

        redis-conf:
          augeas.change:
            - changes:
              - set /files/etc/redis/redis.conf/bind 0.0.0.0

    .. note::

        Use the ``context`` parameter to specify the file you want to
        manipulate. This way you don't have to include this in the changes
        every time:

        .. code-block:: yaml

            redis-conf:
              augeas.change:
                - context: /files/etc/redis/redis.conf
                - changes:
                  - set bind 0.0.0.0
                  - set databases 4
                  - set maxmemory 1G

    Augeas is aware of a lot of common configuration files and their syntax.
    It knows the difference between for example ini and yaml files, but also
    files with very specific syntax, like the hosts file. This is done with
    *lenses*, which provide mappings between the Augeas tree and the file.

    There are many `preconfigured lenses`_ that come with Augeas by default,
    and they specify the common locations for configuration files. So most
    of the time Augeas will know how to manipulate a file. In the event that
    you need to manipulate a file that Augeas doesn't know about, you can
    specify the lens to use like this:

    .. code-block:: yaml

        redis-conf:
          augeas.change:
            - lens: redis
            - context: /files/etc/redis/redis.conf
            - changes:
              - set bind 0.0.0.0

    .. note::

        Even though Augeas knows that ``/etc/redis/redis.conf`` is a Redis
        configuration file and knows how to parse it, it is recommended to
        specify the lens anyway. This is because by default, Augeas loads all
        known lenses and their associated file paths. All these files are
        parsed when Augeas is loaded, which can take some time. When specifying
        a lens, Augeas is loaded with only that lens, which speeds things up
        quite a bit.

    .. _preconfigured lenses: http://augeas.net/stock_lenses.html

    A more complex example, this adds an entry to the services file for Zabbix,
    and removes an obsolete service:

    .. code-block:: yaml

        zabbix-service:
          augeas.change:
            - lens: services
            - context: /files/etc/services
            - changes:
              - ins service-name after service-name[last()]
              - set service-name[last()] zabbix-agent
              - set service-name[. = 'zabbix-agent']/#comment "Zabbix Agent service"
              - set service-name[. = 'zabbix-agent']/port 10050
              - set service-name[. = 'zabbix-agent']/protocol tcp
              - rm service-name[. = 'im-obsolete']
            - unless: grep "zabbix-agent" /etc/services

    .. warning::

        Don't forget the ``unless`` here, otherwise a new entry will be added
        every time this state is run.

    '''
    ret = {'name': name, 'result': False, 'comment': '', 'changes': {}}

    if not changes or not isinstance(changes, list):
        ret['comment'] = '\'changes\' must be specified as a list'
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Executing commands'
        if context:
            ret['comment'] += ' in file "{1}"'.format(context)
        ret['comment'] += "\n".join(changes)
        return ret

    old_file = []
    if context:
        filename = re.sub('^/files|/$', '', context)
        if os.path.isfile(filename):
            file_ = open(filename, 'r')
            old_file = file_.readlines()
            file_.close()

    result = __salt__['augeas.execute'](context=context, lens=lens, commands=changes)
    ret['result'] = result['retval']

    if ret['result'] is False:
        ret['comment'] = 'Error: {0}'.format(result['error'])
        return ret

    if old_file:
        file_ = open(filename, 'r')
        diff = ''.join(difflib.unified_diff(old_file, file_.readlines(), n=0))
        file_.close()

        if diff:
            ret['comment'] = 'Changes have been saved'
            ret['changes'] = diff
        else:
            ret['comment'] = 'No changes made'

    else:
        ret['comment'] = 'Changes have been saved'
        ret['changes'] = changes

    return ret


def setvalue(name, prefix=None, changes=None, **kwargs):
    '''
    .. deprecated:: 2014.7.0
       Use :py:func:`~salt.states.augeas.change` instead.

    Set a value for a specific augeas path
    '''
    ret = {'name': name, 'result': False, 'comment': '', 'changes': {}}

    args = []
    if not changes:
        ret['comment'] = '\'changes\' must be specified'
        return ret
    else:
        if not isinstance(changes, list):
            ret['comment'] = '\'changes\' must be formatted as a list'
            return ret
        for change_ in changes:
            if not isinstance(change_, dict) or len(change_) > 1:
                ret['comment'] = 'Invalidly-formatted change'
                return ret
            key = next(iter(change_))
            args.extend([key, change_[key]])

    if prefix is not None:
        args.insert(0, 'prefix={0}'.format(prefix))

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Calling setvalue with {0}'.format(args)
        return ret

    call = __salt__['augeas.setvalue'](*args)

    ret['result'] = call['retval']

    if ret['result'] is False:
        ret['comment'] = 'Error: {0}'.format(call['error'])
        return ret

    ret['comment'] = 'Success'
    for change_ in changes:
        ret['changes'].update(change_)
    return ret
