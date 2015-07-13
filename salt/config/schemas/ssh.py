# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    salt.config.schemas.ssh
    ~~~~~~~~~~~~~~~~~~~~~~~

    Salt SSH related configuration schemas
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt libs
from salt.utils.config import (Configuration,
                               StringConfig,
                               IntegerConfig,
                               SecretConfig,
                               OneOfConfig,
                               IPv4Config,
                               HostnameConfig,
                               PortConfig,
                               BooleanConfig,
                               RequirementsItem,
                               DictConfig,
                               AnyOfConfig
                               )
from salt.config.schemas.minion import MinionConfiguration


class RosterEntryConfig(Configuration):
    '''
    Schema definition of a Salt SSH Roster entry
    '''

    title = 'Roster Entry'
    description = 'Salt SSH roster entry definition'

    host = StringConfig(title='Host',
                        description='The IP address or DNS name of the remote host',
                        # Pretty naive pattern matching
                        pattern=r'^((\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})|([A-Za-z0-9][A-Za-z0-9\.\-]{1,255}))$',
                        min_length=1,
                        required=True)
    port = PortConfig(title='Port',
                      description='The target system\'s ssh port number',
                      default=22)
    user = StringConfig(title='User',
                        description='The user to log in as. Defaults to root',
                        default='root',
                        min_length=1,
                        required=True)
    passwd = SecretConfig(title='Password',
                          description='The password to log in with')
    priv = StringConfig(title='Private Key',
                        description='File path to ssh private key, defaults to salt-ssh.rsa')
    passwd_or_priv_requirement = AnyOfConfig(items=(RequirementsItem(requirements=['passwd']),
                                                    RequirementsItem(requirements=['priv'])))(flatten=True)
    sudo = BooleanConfig(title='Sudo',
                         description='run command via sudo. Defaults to False',
                         default=False)
    timeout = IntegerConfig(title='Timeout',
                            description=('Number of seconds to wait for response '
                                         'when establishing an SSH connection'))
    thin_dir = StringConfig(title='Thin Directory',
                            description=('The target system\'s storage directory for Salt '
                                         'components. Defaults to /tmp/salt-<hash>.'))
    minion_opts = DictConfig(title='Minion Options',
                             description='Dictionary of minion options',
                             properties=MinionConfiguration())


class RosterConfig(Configuration):
    title = 'Roster Configuration'
    description = 'Roster entries definition'

    roster_entries = DictConfig(
        pattern_properties={
            r'^([^:]+)$': RosterEntryConfig()})(flatten=True)
