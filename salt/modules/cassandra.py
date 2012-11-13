'''
Cassandra NoSQL Database Module

REQUIREMENT 1:

The location of the 'nodetool' command, host, and thrift port
needs to be specified via pillar.

    cassandra.nodetool: /usr/local/bin/nodetool
    cassandra.host: localhost
    cassandra.thrift_port: 9160

REQUIREMENT 2:

The python module, 'pycassa', also needs to be installed on the
minion.
'''
# Import Python libs
import logging
log = logging.getLogger(__name__)

load = False
try:
    from pycassa.system_manager import SystemManager
    load = True
except ImportError:
    pass

__outputter__ = {
  'compactionstats': 'txt',
  'tpstats': 'txt',
  'netstats': 'txt',
  'info': 'txt',
  'ring': 'txt',
}

nt = ''
host = ''
thrift_port = ''


def __virtual__():
    '''
    Only load if pycassa is available and the system is configured
    '''
    if not load:
        return False

    nt = __salt__['config.option']('cassandra.nodetool')
    host = __salt__['config.option']('cassandra.host')
    thrift_port = str(__salt__['config.option']('cassandra.thrift_port'))

    if nt and host and thrift_port:
        return 'cassandra'
    return False


def _nodetool(cmd):
    '''
    Internal cassandra nodetool wrapper. Some functions are not
    available via pycassa so we must rely on nodetool.
    '''
    return __salt__['cmd.run_stdout']('{0} -h {1} {2}'.format(nt, host, cmd))


def _sys_mgr():
    '''
    Return a pycassa system manager connection object
    '''
    return SystemManager('{0}:{1}'.format(host, thrift_port))


def compactionstats():
    '''
    Return compactionstats info

    CLI Example::

        salt '*' cassandra.compactionstats
    '''
    return _nodetool('compactionstats')


def version():
    '''
    Return the cassandra version

    CLI Example::

        salt '*' cassandra.version
    '''
    return _nodetool('version')


def netstats():
    '''
    Return netstats info

    CLI Example::

        salt '*' cassandra.netstats
    '''
    return _nodetool('netstats')


def tpstats():
    '''
    Return tpstats info

    CLI Example::

        salt '*' cassandra.tpstats
    '''
    return _nodetool('tpstats')


def info():
    '''
    Return cassandra node info

    CLI Example::

        salt '*' cassandra.info
    '''
    return _nodetool('info')


def ring():
    '''
    Return cassandra ring info

    CLI Example::

        salt '*' cassandra.ring
    '''
    return _nodetool('ring')


def keyspaces():
    '''
    Return existing keyspaces

    CLI Example::

        salt '*' cassandra.keyspaces
    '''
    sys = _sys_mgr()
    return sys.list_keyspaces()


def column_families(keyspace=None):
    '''
    Return existing column families for all keyspaces
    or just the provided one.

    CLI Example::

        salt '*' cassandra.column_families
        salt '*' cassandra.column_families <keyspace>
    '''
    sys = _sys_mgr()
    ks = sys.list_keyspaces()

    if keyspace:
        if keyspace in ks:
            return sys.get_keyspace_column_families(keyspace).keys()
        else:
            return None
    else:
        ret = {}
        for k in ks:
            ret[k] = sys.get_keyspace_column_families(k).keys()

        return ret


def column_family_definition(keyspace=None, column_family=None):
    '''
    Return a dictionary of column family definitions for the given
    keyspace/column_family

    CLI Example::

        salt '*' cassandra.column_family_definition <keyspace> <column_family>

    '''
    sys = _sys_mgr()

    try:
        return vars(sys.get_keyspace_column_families(keyspace)[column_family])
    except:
        log.debug('Invalid Keyspace/CF combination')
        return None
