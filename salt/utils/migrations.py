'''
Migration tools
'''
# import
import os.path

def migrate_paths(master_or_minion = 'minion'):
    '''
    Migrate old minion and master file paths to new ones.
    '''
    oldsock_dir = '/var/run/salt'
    newsock_dir = '/var/run/salt/{0}'.format(master_or_minion)
    
    oldpki_dir = '/etc/salt/pki'
    newpki_dir = '/etc/salt/pki/{0}'.format(master_or_minion)

    oldcache_dir = '/var/cache/salt'
    newcache_dir = '/var/cache/salt/{0}'.format(master_or_minion)

    if not os.path.exists(newsock_dir):
        print 'migrate sock stuff'

    if not os.path.exists(newpki_dir):
        print 'migrate pki stuff'

    if not os.path.exists(newcache_dir):
        print 'migrate cache stuff'

