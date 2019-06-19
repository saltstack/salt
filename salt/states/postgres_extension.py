# -*- coding: utf-8 -*-
'''
Management of PostgreSQL extensions
===================================

A module used to install and manage PostgreSQL extensions.

.. code-block:: yaml

    adminpack:
      postgres_extension.present


.. versionadded:: 2014.7.0
'''
from __future__ import absolute_import, unicode_literals, print_function

# Import Python libs
import logging

# Import salt libs
from salt.modules import postgres

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if the postgres module is present
    '''
    if 'postgres.create_extension' not in __salt__:
        return (False, 'Unable to load postgres module.  Make sure `postgres.bins_dir` is set.')
    return True


def present(name,
            if_not_exists=None,
            schema=None,
            ext_version=None,
            from_version=None,
            user=None,
            maintenance_db=None,
            db_user=None,
            db_password=None,
            db_host=None,
            db_port=None):
    '''
    Ensure that the named extension is present.

    .. note::

        Before you can use the state to load an extension into a database, the
        extension's supporting files must be already installed.

    For more information about all of these options see ``CREATE EXTENSION`` SQL
    command reference in the PostgreSQL documentation.

    name
        The name of the extension to be installed

    if_not_exists
        Add an ``IF NOT EXISTS`` parameter to the DDL statement

    schema
        Schema to install the extension into

    ext_version
        Version to install

    from_version
        Old extension version if already installed

    user
        System user all operations should be performed on behalf of

    maintenance_db
        Database to act on

    db_user
        Database username if different from config or default

    db_password
        User password if any password for a specified user

    db_host
        Database host if different from config or default

    db_port
        Database port if different from config or default
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Extension {0} is already present'.format(name)}
    db_args = {
        'maintenance_db': maintenance_db,
        'runas': user,
        'user': db_user,
        'password': db_password,
        'host': db_host,
        'port': db_port,
    }
    # check if extension exists
    mode = 'create'
    mtdata = __salt__['postgres.create_metadata'](
        name,
        schema=schema,
        ext_version=ext_version,
        **db_args)

    # The extension is not present, install it!
    toinstall = postgres._EXTENSION_NOT_INSTALLED in mtdata
    if toinstall:
        mode = 'install'
    toupgrade = False
    if postgres._EXTENSION_INSTALLED in mtdata:
        for flag in [
            postgres._EXTENSION_TO_MOVE,
            postgres._EXTENSION_TO_UPGRADE
        ]:
            if flag in mtdata:
                toupgrade = True
                mode = 'upgrade'
    cret = None
    if toinstall or toupgrade:
        if __opts__['test']:
            ret['result'] = None
            if mode:
                ret['comment'] = 'Extension {0} is set to be {1}ed'.format(
                    name, mode).replace('eed', 'ed')
            return ret

        cret = __salt__['postgres.create_extension'](
            name=name,
            if_not_exists=if_not_exists,
            schema=schema,
            ext_version=ext_version,
            from_version=from_version,
            **db_args)
    if cret:
        if mode.endswith('e'):
            suffix = 'd'
        else:
            suffix = 'ed'
        ret['comment'] = 'The extension {0} has been {1}{2}'.format(name, mode, suffix)
        ret['changes'][name] = '{0}{1}'.format(mode.capitalize(), suffix)
    elif cret is not None:
        ret['comment'] = 'Failed to {1} extension {0}'.format(name, mode)
        ret['result'] = False

    return ret


def absent(name,
           if_exists=None,
           restrict=None,
           cascade=None,
           user=None,
           maintenance_db=None,
           db_user=None,
           db_password=None,
           db_host=None,
           db_port=None):
    '''
    Ensure that the named extension is absent.

    name
        Extension name of the extension to remove

    if_exists
        Add if exist slug

    restrict
        Add restrict slug

    cascade
        Drop on cascade

    user
        System user all operations should be performed on behalf of

    maintenance_db
        Database to act on

    db_user
        Database username if different from config or default

    db_password
        User password if any password for a specified user

    db_host
        Database host if different from config or default

    db_port
        Database port if different from config or default
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    db_args = {
        'maintenance_db': maintenance_db,
        'runas': user,
        'host': db_host,
        'user': db_user,
        'port': db_port,
        'password': db_password,
    }
    # check if extension exists and remove it
    exists = __salt__['postgres.is_installed_extension'](name, **db_args)
    if exists:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Extension {0} is set to be removed'.format(name)
            return ret
        if __salt__['postgres.drop_extension'](name,
                                               if_exists=if_exists,
                                               restrict=restrict,
                                               cascade=cascade,
                                               **db_args):
            ret['comment'] = 'Extension {0} has been removed'.format(name)
            ret['changes'][name] = 'Absent'
            return ret
        else:
            ret['result'] = False
            ret['comment'] = 'Extension {0} failed to be removed'.format(name)
            return ret
    else:
        ret['comment'] = 'Extension {0} is not present, so it cannot ' \
                         'be removed'.format(name)

    return ret
