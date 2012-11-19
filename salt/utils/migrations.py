'''
Migration tools
'''
# import
import os.path

def migrate_paths(opts):
    '''
    Migrate old minion and master pki file paths to new ones.
    '''
    oldpki_dir = '/etc/salt/pki'
    
    if opts['default_include'].startswith('minion'):
        newpki_dir = '/etc/salt/pki/minion'
        if os.path.exists(oldpki_dir) and os.path.exists(newpki_dir):
            pass


    if not os.path.exists(newpki_dir):
        print 'migrate pki stuff'

