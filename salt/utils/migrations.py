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
    newpki_dir = opts['pki_dir']
    
    if opts['default_include'].startswith('master'):
        keepers = ['master.pem',
                    'master.pub',
                    'syndic_master.pub',
                    'minions',
                    'minions_pre',
                    'minions_rejected',
                    ]
        if not os.path.exists(newpki_dir):
            os.makedirs(newpki_dir)
        for item in keepers:
            if (os.path.exists(os.path.join(oldpki_dir, item)) == True and 
                    os.path.exists(os.path.join(newpki_dir, item)) == False):
                shutil.move('{0}/{1}'.format(oldpki_dir, item),
                            '{0}/{1}'.format(newpki_dir, item))
                    
    if opts['default_include'].startswith('minion'):
        keepers = ['minion_master.pub',
                    'minion.pem',
                    'minion.pub',
                    ]
        if not os.path.exists(newpki_dir):
            os.makedirs(newpki_dir)
        for item in keepers:
            if (os.path.exists(os.path.join(oldpki_dir, item)) == True and 
                    os.path.exists(os.path.join(newpki_dir, item)) == False):
                shutil.move('{0}/{1}'.format(oldpki_dir, item),
                            '{0}/{1}'.format(newpki_dir, item))

