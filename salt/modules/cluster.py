'''
The cluster module is used to distribute and activate salt HA cluster
components
'''
# Import Python Modules
import os
# Import Salt Modules
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
        if cluster_addr:
            passwd = master_pem.split()[12][:12]
            cmd = 'ifconfig ' + self.opts['cluster_interface']\
                + ' | grep "inet "'\
                + ' | cut -d: -f2 | cut -d" " -f1'
            s_addr = subprocess.Popen(cmd,
                                      shell=True,
                                      stdout=subprocess.PIPE,
                                      ).communicate()[0]
            cmd = 'ucarp -i ' + opts['cluster_interface'] + ' -s ' + s_addr\
                + ' -v 10 -p ' + passwd + ' -a ' + opts['cluster_addr']\
                + ' -u /usr/libexec/salt/clust-up '\
                + ' -d /usr/libexec/salt/clust-down -r 3 -B -z'
            g_cmd = 'ps aux | grep "' + cmd + '"'
            ret = subprocess.call(g_cmd, shell=True)
            if not ret:
                # The ucarp interface is not running, start it
                subprocess.Popen(cmd, shell=True)
