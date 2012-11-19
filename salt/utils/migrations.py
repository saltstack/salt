'''
Migration tools
'''
# import
import os.path
import shutil

def migrate_paths(opts):
    '''
    Migrate old minion and master pki file paths to new ones.
    '''
    oldpki_dir = '/etc/salt/pki'
    
    if opts['default_include'].startswith('master'):
        keepers= ['master.pem',
                'master.pub',
                'syndic_master.pub',
                'minions',
                'minions_pre',
                'minions_rejected',
                ]
        newpki_dir = opts['pki_dir']:
        if not os.path.exists(newpki_dir):
            os.makedirs(newpki_dir)
        for item in keepers:
            if os.path.exists('{0}/{1}'.format(oldpki_dir, item) and not os.path.exists('{0}/master/{1}'.format(newpki_dir, item):
                shutil.move('{0}/{1}'.format(oldpki_dir, item), '{0}/master/{1}'.format(newpki_dir, item)

