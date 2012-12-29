'''
Runner to manage Windows software repo
'''

# Import python libs
import os
import os.path
import yaml
from pprint import pprint
import msgpack

# Import salt libs
import salt.output
import salt.utils
import logging
import salt.minion

log = logging.getLogger(__name__)


def genrepo():
    '''
    Generate win_repo_cachefile based on sls files in the win_repo
    '''
    ret = {}
    repo = __opts__['win_repo']
    winrepo = __opts__['win_repo_mastercachefile']
    for root, dirs, files in os.walk(repo):
        for name in files:
            if name.endswith('.sls'):
                with salt.utils.fopen(os.path.join(root, name), 'r') as slsfile:
                    try:
                        config = yaml.safe_load(slsfile.read()) or {}
                    except yaml.parser.ParserError as exc:
                        # log.debug doesn't seem to be working
                        # delete the following print statement 
                        # when log.debug works
                        log.debug('Failed to compile'
                                '{0}: {1}'.format(os.path.join(root, name), exc))
                        print 'Failed to compile {0}: {1}'.format(os.path.join(root, name), exc)
                if config:
                    ret.update(config)
    with salt.utils.fopen(os.path.join(repo, winrepo), 'w') as repo:
        repo.write(msgpack.dumps(ret))
    salt.output.display_output(ret, 'pprint', __opts__)
    return ret

def update_git_repos():
    '''
    Checkout git repos containing Windows Software Package Definitions
    '''
    ret = {}
    mminion = salt.minion.MasterMinion(__opts__)
    repo = __opts__['win_repo']
    gitrepos = __opts__['win_gitrepos']
    for gitrepo in gitrepos:
        if '/' in gitrepo:
            targetname = gitrepo.split('/')[-1]
        else:
            targetname = gitrepo
        gittarget = os.path.join(repo, targetname)
        result = mminion.states['git.latest'](gitrepo, target=gittarget, force=True)
        ret[result['name']] = result['result']
    salt.output.display_output(ret, 'pprint', __opts__)
    return ret
