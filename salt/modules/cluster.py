'''
The cluster module is used to distribute and activate salt HA cluster
components
'''

import os

import salt.config


def distrib(minions,
            master_conf,
            master_pem,
            conf_file):
    '''
    Set up this minion as a failover master - only intended for use by the
    cluster interface
    '''
    # Write the master config file
    open(conf_file, 'w+').write(master_conf)
    # Get the distributed master config opts
    opts = salt.config.master_config(conf_file)
    # Commit the minions
    minion_dir = os.path.join(opts['pki_dir'], 'minions')
    if not os.path.isdir(minion_dir):
        os.makedirs(minion_dir)
    for minion in minions:
        open(os.path.join(minion_dir, minion),
                'w+').write(minions[minion])
    # Commit the master.pem and verify the cluster interface
    if master_pem:
        open(os.path.join(opts['pki_dir'],
            'master.pem'), 'w+').write(master_pem)
