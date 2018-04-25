# -*- coding: utf-8 -*-
'''
Module for check or migrate database for Openstack projects
==================


:depends:   - oslo_db, alembic, Openstack Python module

The openstack_db_mng module is used to check and migrate database for Openstacks projects:
keystone, nova, cinder, heat, neutron, glance, mistral, manila

:codeauthor: David Homolka <david.homolka@ultimum.io>
'''
from __future__ import absolute_import

# Import python libs
import logging
import os.path
import warnings

# Import Salt libs
import salt.utils
from salt.exceptions import SaltInvocationError, SaltException

# Import third party libs
HAS_MODULES = False
HAS_MIGRATE = False
HAS_ALEMBIC = False
try:
    import migrate
    from migrate import exceptions as migrate_exceptions
    from migrate.versioning import api as migrate_api
    import osprofiler
    HAS_MIGRATE = True
except ImportError:
    pass
try:
    from alembic import config as alembic_config
    from alembic.script.base import ScriptDirectory
    from alembic import migration as alembic_migration
    HAS_ALEMBIC = True
except ImportError:
    pass
try:
    from oslo_db import options as db_options
    from oslo_db.sqlalchemy import enginefacade
    from oslo_db.sqlalchemy import session as sqlalchemy_session
    HAS_MODULES = True
except ImportError:
    pass

logging.basicConfig(level='ERROR')
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'openstack_db_mng'


def __virtual__():
    '''
    Only run this module if python modules is installed
    (package python-alembic, python-migrate, python-oslo.config,
     python-oslo.db, python-osprofiler).
    '''
    if HAS_MODULES:
        return __virtualname__
    return (False, 'The openstack_db_mng execution module cannot be loaded: package python-oslo.db not installed.')


def _keystone_check_db_migration(connection):
    '''
    Check the database migration.

    Returns:
        True if database is different version, else False.

    Args:
        connection: A string - url to database

    '''
    if HAS_MIGRATE is False:
        raise SaltException('Package python-migrate or python-osprofiler could not be found')
    try:
        from keystone.common.sql import upgrades as keystone_migration
        from oslo_config import cfg
        conf = cfg.CONF
    except ImportError:
        raise SaltException('Keystone or python-oslo.config package could not be found')
    current_version = None
    repo_version = None

    try:
        repo_path = keystone_migration.find_repo(keystone_migration.LEGACY_REPO)
        repo_version = int(migrate.versioning.repository.Repository(str(repo_path)).latest)
    except AttributeError as exc:
        raise SaltInvocationError("Error:'{0}'".format(exc))

    try:
        db_options.set_defaults(
            conf,
            connection="{0}".format(connection))
        # Configure OSprofiler options
        osprofiler.opts.set_defaults(conf, enabled=False, trace_sqlalchemy=False)
        current_version = int(keystone_migration.get_db_version())
    except AttributeError as exc:
        raise SaltInvocationError("Error:'{0}'".format(exc))

    if current_version is not None and repo_version is not None:
        return current_version != repo_version
    else:
        raise SaltInvocationError("Keystone current or repo databases versions could not be found")


def _nova_check_db_migration(connection):
    '''
    Check the database migration.

    Returns:
        True if database is different version, else False.

    Args:
        connection: A string - url to database

    '''
    if HAS_MIGRATE is False:
        raise SaltException('Package python-migrate or python-osprofiler could not be found')
    try:
        from nova.db.sqlalchemy import migration as nova_migration
        from oslo_config import cfg
        conf = cfg.CONF
    except ImportError:
        raise SaltException('Nova or python-oslo.config package could not be found')

    current_version = None
    repo_version = None

    try:
        repo = nova_migration._find_migrate_repo()  # pylint: disable=W0212
        repo_version = int(repo.latest)
    except AttributeError as exc:
        raise SaltInvocationError("Error:'{0}'".format(exc))

    try:
        db_options.set_defaults(
            conf,
            connection="{0}".format(connection))
        current_version = int(nova_migration.db_version())
    except AttributeError as exc:
        raise SaltInvocationError("Error:'{0}'".format(exc))

    if current_version is not None and repo_version is not None:
        return current_version != repo_version
    else:
        raise SaltInvocationError("Nova current or repo databases versions could not be found")


def _cinder_check_db_migration(connection):
    '''
    Check the database migration.

    Returns:
        True if database is different version, else False.

    Args:
        connection: A string - url to database

    '''
    if HAS_MIGRATE is False:
        raise SaltException('Package python-migrate or python-osprofiler could not be found')
    try:
        import cinder
        from oslo_config import cfg
        conf = cfg.CONF
    except ImportError:
        raise SaltException('Cinder or python-oslo.config package could not be found')
    current_version = None
    repo_version = None

    try:
        repo_path = os.path.join(
            os.path.abspath(os.path.dirname(cinder.__file__)),
            'db',
            'sqlalchemy',
            'migrate_repo',
        )
        repo_version = int(migrate.versioning.repository.Repository(str(repo_path)).latest)
    except AttributeError as exc:
        raise SaltInvocationError("Error:'{0}'".format(exc))

    try:
        db_options.set_defaults(
            conf,
            connection="{0}".format(connection))
        facade = sqlalchemy_session.EngineFacade(conf.database.connection, **dict(conf.database))
    except AttributeError as exc:
        raise SaltInvocationError("Error:'{0}'".format(exc))

    try:
        current_version = int(migrate_api.db_version(facade.get_engine(), repo_path))
    except migrate_exceptions.DatabaseNotControlledError:
        current_version = 0

    if current_version is not None and repo_version is not None:
        return current_version != repo_version
    else:
        raise SaltInvocationError("Cinder current or repo databases versions could not be found")


def _heat_check_db_migration(connection):
    '''
    Check the database migration.

    Returns:
        True if database is different version, else False.

    Args:
        connection: A string - url to database

    '''
    if HAS_MIGRATE is False:
        raise SaltException('Package python-migrate or python-osprofiler could not be found')
    try:
        import heat
        from heat.db.sqlalchemy import migration as heat_migration
        from oslo_config import cfg
        conf = cfg.CONF
    except ImportError:
        raise SaltException('Heat or python-oslo.config package could not be found')
        # module.fail_json(msg="heat package could not be found")
    current_version = None
    repo_version = None

    try:
        repo_path = os.path.join(os.path.dirname(heat.__file__),
                                 'db', 'sqlalchemy', 'migrate_repo')
        repo_version = int(migrate.versioning.repository.Repository(str(repo_path)).latest)
    except AttributeError as exc:
        raise SaltInvocationError("Error:'{0}'".format(exc))
    try:
        db_options.set_defaults(
            conf,
            connection="{0}".format(connection))
        db_context = enginefacade.transaction_context()
        db_context.configure(**conf.database)
        facade = db_context.get_legacy_facade()
        current_version = int(heat_migration.db_version(facade.get_engine()))
    except AttributeError as exc:
        raise SaltInvocationError("Error:'{0}'".format(exc))

    if current_version is not None and repo_version is not None:
        return current_version != repo_version
    else:
        raise SaltInvocationError("Heat current or repo databases versions could not be found")


def _neutron_check_db_migration(connection):
    '''
    Check the database migration.

    Returns:
        True if database is different version, else False.

    Args:
        connection: A string - url to database

    '''
    if HAS_ALEMBIC is False:
        raise SaltException('Package python-alembic could not be found')
    try:
        import neutron
    except ImportError:
        raise SaltException('Neutron package could not be found')
    current_heads = None
    contract_head = None
    expand_path = None

    try:
        engine = sqlalchemy_session.create_engine(connection)
        with engine.connect() as connect:
            context = alembic_migration.MigrationContext.configure(connect)
            current_heads = context.get_current_heads()
        contract_path = os.path.join(
            os.path.dirname(neutron.__file__), 'db', 'migration', 'alembic_migrations', 'versions', 'CONTRACT_HEAD')
        expand_path = os.path.join(
            os.path.dirname(neutron.__file__), 'db', 'migration', 'alembic_migrations', 'versions', 'EXPAND_HEAD')
        with salt.utils.fopen(contract_path, 'r') as contract_file:
            contract_head = contract_file.readlines()
        with salt.utils.fopen(expand_path, 'r') as expand_file:
            expand_head = expand_file.readlines()
    except Exception as exc:
        raise SaltInvocationError("Error:'{0}'".format(exc))

    if current_heads is not None and contract_head is not None and expand_head is not None:
        if len(current_heads) == 2:
            return(
                not(((current_heads[0] != expand_head) and (current_heads[1] != contract_head))
                    or ((current_heads[0] != contract_head) and (current_heads[1] != expand_head))))
        return True

    raise SaltInvocationError("Neutron current or repo databases heads could not be found")


def _glance_check_db_migration(connection):
    '''
    Check the database migration.

    Returns:
        True if database is different version, else False.

    Args:
        connection: A string - url to database

    '''
    if HAS_ALEMBIC is False:
        raise SaltException('Package python-alembic could not be found')
    try:
        from glance.db.sqlalchemy import alembic_migrations
        from glance.db import migration as glance_migration
        from oslo_config import cfg
        conf = cfg.CONF
    except ImportError:
        raise SaltException('Glance or python-oslo.config package could not be found')

    current_heads = None
    contract_head = None
    expand_head = None

    try:
        db_options.set_defaults(
            conf,
            connection="{0}".format(connection))
    except AttributeError as exc:
        raise SaltInvocationError("Error:'{0}'".format(exc))

    try:
        warnings.filterwarnings("ignore")
        contract_head = alembic_migrations.get_alembic_branch_head(glance_migration.CONTRACT_BRANCH)
        expand_head = alembic_migrations.get_alembic_branch_head(glance_migration.EXPAND_BRANCH)
        current_heads = alembic_migrations.get_current_alembic_heads()
    except Exception as exc:
        raise SaltInvocationError("Error:'{0}'".format(exc))

    if current_heads is not None and contract_head is not None and expand_head is not None:
        if '_expand' in expand_head:
            expand_head = str(expand_head).replace("_expand", "")
        return expand_head not in current_heads
    else:
        raise SaltInvocationError("Glance current or repo databases heads could not be found")


def _mistral_check_db_migration(connection):
    '''
    Check the database migration.

    Returns:
        True if database is different version, else False.

    Args:
        connection: A string - url to database

    '''
    if HAS_ALEMBIC is False:
        raise SaltException('Package python-alembic could not be found')
    if HAS_MIGRATE is False:
        raise SaltException('Package python-migrate or python-osprofiler could not be found')
    try:
        import mistral
    except ImportError:
        raise SaltException('Mistral package could not be found')
        # module.fail_json(msg="heat package could not be found")
    current_version = None
    repo_version = None

    try:
        repo_path = os.path.join(
            os.path.dirname(mistral.__file__), 'db', 'sqlalchemy', 'migration', 'alembic_migrations', 'versions')
        repo_version = int(migrate.versioning.version.Collection(str(repo_path)).latest)
    except AttributeError as exc:
        raise SaltInvocationError("Error:'{0}'".format(exc))

    try:
        engine = sqlalchemy_session.create_engine(connection)
        with engine.connect() as connect:
            context = alembic_migration.MigrationContext.configure(connect)
            if context.get_current_heads():
                current_version = int(context.get_current_heads()[0])
            else:
                current_version = 0
    except Exception as exc:
        raise SaltInvocationError("Error:'{0}'".format(exc))

    if current_version is not None and repo_version is not None:
        return current_version != repo_version
    else:
        raise SaltInvocationError("Mistral current or repo databases versions could not be found")


def _manila_check_db_migration(connection):
    '''
    Check the database migration.

    Returns:
        True if database is different version, else False.

    Args:
        connection: A string - url to database

    '''
    if HAS_ALEMBIC is False:
        raise SaltException('Package python-alembic could not be found')
    try:
        import manila
        from manila.db.migrations.alembic import migration as manila_migration
        from oslo_config import cfg
        conf = cfg.CONF
    except ImportError:
        raise SaltException('Manila or python-oslo.config package could not be found')
        # module.fail_json(msg="heat package could not be found")
    current_version = None
    repo_version = []

    try:
        path = os.path.join(os.path.dirname(manila.__file__), 'db', 'migrations', 'alembic.ini')
        config = alembic_config.Config(path)
        script = ScriptDirectory.from_config(config)
        heads = script.get_revisions("head")
        for rev in heads:
            repo_version.append(rev.revision)
    except AttributeError as exc:
        raise SaltInvocationError("Error:'{0}'".format(exc))

    try:
        db_options.set_defaults(
            conf,
            connection="{0}".format(connection))
        current_version = manila_migration.version()
    except AttributeError as exc:
        raise SaltInvocationError("Error:'{0}'".format(exc))

    if repo_version:
        return current_version not in repo_version
    else:
        raise SaltInvocationError("Manila repo databases versions could not be found")


SERVICE_DB_CHECK = {
    'keystone': _keystone_check_db_migration,
    'nova': _nova_check_db_migration,
    'cinder': _cinder_check_db_migration,
    'heat': _heat_check_db_migration,
    'neutron': _neutron_check_db_migration,
    'glance': _glance_check_db_migration,
    'mistral': _mistral_check_db_migration,
    'manila': _manila_check_db_migration,
}

SERVICE_DB_MIGRATE = {
    'keystone': ['keystone-manage db_sync'],
    'nova': ['nova-manage api_db sync',
             'nova-manage cell_v2 map_cell0',
             'nova-manage db sync'],
    'cinder': ['cinder-manage db sync'],
    'heat': ['heat-manage db_sync'],
    'neutron': ['neutron-db-manage upgrade %s head'],
    'glance': ['glance-manage db_sync'],
    'mistral': ['mistral-db-manage upgrade head'],
    'manila': ['manila-manage db sync'],
}


def check_db_migration(service, connection):
    '''
    Check the database migration.

    Returns:
        True if database is different version, else False.

    Args:
        service: A string - name Openstack service(keystone, nova, cinder, heat, neutron, glance, mistral, manila)
        connection: A string - url to database

    CLI Example:

    .. code-block:: bash

        salt '*' openstack_db_mng.check_db_migration 'keystone' 'mysql://keystone:keystone@localhost/keystone'

    '''
    if service in SERVICE_DB_CHECK:
        return SERVICE_DB_CHECK[service](connection)
    else:
        raise SaltInvocationError("Invalid service argument")


def db_migration(service, mysql_engine=None, user=None, group=None):
    '''
    Check the database migration.

    Returns:
        True if database is different version, else False.

    Args:
        service: A string - name Openstack service(keystone, nova, cinder, heat, neutron, glance, mistral, manila)
        mysql_engine: A string(only used for neutron)
                      - MySQL storage engine of current existing tables(innodb, ndbcluster)
        user: User to run migration command as.

        group: Group to run migration command as.

    CLI Example:

    .. code-block:: bash

        salt '*' openstack_db_mng.db_migration 'keystone'
        salt '*' openstack_db_mng.db_migration 'neutron' 'ndbcluster'

    '''

    if service in SERVICE_DB_MIGRATE:
        for cmd in SERVICE_DB_MIGRATE[service]:
            if str(service) == 'neutron':
                if mysql_engine is None:
                    cmd = cmd % ''
                else:
                    sql_engine = '--mysql-engine {0}'.format(mysql_engine)
                    cmd = cmd % sql_engine

            out = __salt__['cmd.run_all'](cmd, runas=user, group=group, python_shell=False)
            if out['retcode'] > 0 and out['stderr'] != '':
                return (False, 'Error command: {0}\n{1}'.format(cmd, out['stderr']))
    else:
        raise SaltInvocationError("Invalid service argument")

    return True
