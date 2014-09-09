# -*- coding: utf-8 -*-
'''
Management of MySQL users
=========================

:depends:   - MySQLdb Python module
:configuration: See :py:mod:`salt.modules.mysql` for setup instructions.

.. code-block:: yaml

    frank:
      mysql_user.present:
        - host: localhost
        - password: bobcat


.. versionadded:: 0.16.2
    Authentication overrides have been added.

The MySQL authentication information specified in the minion config file can be
overridden in states using the following arguments: ``connection_host``,
``connection_port``, ``connection_user``, ``connection_pass``,
``connection_db``, ``connection_unix_socket``, ``connection_default_file`` and
``connection_charset``.

.. code-block:: yaml

    frank:
      mysql_user.present:
        - host: localhost
        - password: "bob@cat"
        - connection_user: someuser
        - connection_pass: somepass
        - connection_charset: utf8
        - saltenv:
          - LC_ALL: "en_US.utf8"
'''

# Import python libs
import sys

# Import salt libs
import salt.utils


def __virtual__():
    '''
    Only load if the mysql module is in __salt__
    '''
    return 'mysql.user_create' in __salt__


def _get_mysql_error():
    '''
    Look in module context for a MySQL error. Eventually we should make a less
    ugly way of doing this.
    '''
    return sys.modules[
        __salt__['test.ping'].__module__
    ].__context__.pop('mysql.error', None)


def present(name,
            host='localhost',
            password=None,
            password_hash=None,
            allow_passwordless=False,
            unix_socket=False,
            **connection_args):
    '''
    Ensure that the named user is present with the specified properties. A
    passwordless user can be configured by omitting ``password`` and
    ``password_hash``, and setting ``allow_passwordless`` to ``True``.

    name
        The name of the user to manage

    host
        Host for which this user/password combo applies

    password
        The password to use for this user. Will take precedence over the
        ``password_hash`` option if both are specified.

    password_hash
        The password in hashed form. Be sure to quote the password because YAML
        doesn't like the ``*``. A password hash can be obtained from the mysql
        command-line client like so::

            mysql> SELECT PASSWORD('mypass');
            +-------------------------------------------+
            | PASSWORD('mypass')                        |
            +-------------------------------------------+
            | *6C8989366EAF75BB670AD8EA7A7FC1176A95CEF4 |
            +-------------------------------------------+
            1 row in set (0.00 sec)

    allow_passwordless
        If ``True``, then ``password`` and ``password_hash`` can be omitted to
        permit a passwordless login.

    unix_socket
        If ``True`` and allow_passwordless is ``True`` then will be used unix_socket auth plugin.

    .. note::
        The ``allow_passwordless`` option will be available in version 0.16.2.
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'User {0}@{1} is already present'.format(name, host)}

    passwordless = not any((password, password_hash))

    # check if user exists with the same password (or passwordless login)
    if passwordless:
        if not salt.utils.is_true(allow_passwordless):
            ret['comment'] = 'Either password or password_hash must be ' \
                             'specified, unless allow_passwordless is True'
            ret['result'] = False
            return ret
        else:
            if __salt__['mysql.user_exists'](name, host, passwordless=True, unix_socket=unix_socket,
                                             **connection_args):
                ret['comment'] += ' with passwordless login'
                return ret
            else:
                err = _get_mysql_error()
                if err is not None:
                    ret['comment'] = err
                    ret['result'] = False
                    return ret
    else:
        if __salt__['mysql.user_exists'](name, host, password, password_hash, unix_socket=unix_socket,
                                         **connection_args):
            ret['comment'] += ' with the desired password'
            if password_hash and not password:
                ret['comment'] += ' hash'
            return ret
        else:
            err = _get_mysql_error()
            if err is not None:
                ret['comment'] = err
                ret['result'] = False
                return ret

    # check if user exists with a different password
    if __salt__['mysql.user_exists'](name, host, unix_socket=unix_socket, **connection_args):

        # The user is present, change the password
        if __opts__['test']:
            ret['comment'] = \
                'Password for user {0}@{1} is set to be '.format(name, host)
            ret['result'] = None
            if passwordless:
                ret['comment'] += 'cleared'
                if not salt.utils.is_true(allow_passwordless):
                    ret['comment'] += ', but allow_passwordless != True'
                    ret['result'] = False
            else:
                ret['comment'] += 'changed'
            return ret

        if __salt__['mysql.user_chpass'](name, host,
                                         password, password_hash,
                                         allow_passwordless, unix_socket,
                                         **connection_args):
            ret['comment'] = \
                'Password for user {0}@{1} has been ' \
                '{2}'.format(name, host,
                             'cleared' if passwordless else 'changed')
            ret['changes'][name] = 'Updated'
        else:
            ret['comment'] = \
                'Failed to {0} password for user ' \
                '{1}@{2}'.format('clear' if passwordless else 'change',
                                 name, host)
            err = _get_mysql_error()
            if err is not None:
                ret['comment'] += ' ({0})'.format(err)
            if passwordless and not salt.utils.is_true(allow_passwordless):
                ret['comment'] += '. Note: allow_passwordless must be True ' \
                                  'to permit passwordless login.'
            ret['result'] = False
    else:

        err = _get_mysql_error()
        if err is not None:
            ret['comment'] = err
            ret['result'] = False
            return ret

        # The user is not present, make it!
        if __opts__['test']:
            ret['comment'] = \
                'User {0}@{1} is set to be added'.format(name, host)
            ret['result'] = None
            if passwordless:
                ret['comment'] += ' with passwordless login'
                if not salt.utils.is_true(allow_passwordless):
                    ret['comment'] += ', but allow_passwordless != True'
                    ret['result'] = False
            return ret

        if __salt__['mysql.user_create'](name, host,
                                         password, password_hash,
                                         allow_passwordless, unix_socket=unix_socket,
                                         **connection_args):
            ret['comment'] = \
                'The user {0}@{1} has been added'.format(name, host)
            if passwordless:
                ret['comment'] += ' with passwordless login'
            ret['changes'][name] = 'Present'
        else:
            ret['comment'] = 'Failed to create user {0}@{1}'.format(name, host)
            err = _get_mysql_error()
            if err is not None:
                ret['comment'] += ' ({0})'.format(err)
            ret['result'] = False

    return ret


def absent(name,
           host='localhost',
           **connection_args):
    '''
    Ensure that the named user is absent

    name
        The name of the user to remove
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    # Check if user exists, and if so, remove it
    if __salt__['mysql.user_exists'](name, host, **connection_args):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'User {0}@{1} is set to be removed'.format(
                    name,
                    host)
            return ret
        if __salt__['mysql.user_remove'](name, host, **connection_args):
            ret['comment'] = 'User {0}@{1} has been removed'.format(name, host)
            ret['changes'][name] = 'Absent'
            return ret
        else:
            err = _get_mysql_error()
            if err is not None:
                ret['comment'] = err
                ret['result'] = False
                return ret
    else:
        err = _get_mysql_error()
        if err is not None:
            ret['comment'] = err
            ret['result'] = False
            return ret

    # fallback
    ret['comment'] = (
            'User {0}@{1} is not present, so it cannot be removed'
            ).format(name, host)
    return ret
