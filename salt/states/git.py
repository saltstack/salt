'''
Git repository management

.. code-block:: yaml

    https://github.com/saltstack/salt.git:
      git:
        - latest
        - rev: develop
        - target: /tmp/salt
'''
import logging
import os

log = logging.getLogger(__name__)


def latest(name,
           rev=None,
           target=None,
           runas=None):
    '''
    Make sure the repository is cloned to the given directory and is up to date

    name
        Address of the remote repository as passed to "git clone"
    rev
        The remote branch or revision to checkout after clone / before update
    target
        Name of the target directory where repository is about to be cloned
    runas
        Name of the user performing repository management operations
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    if not target:
        return _fail(ret, '"target" option is required')


    if os.path.isdir(target):
        # git pull is probably required
        log.debug('target {0} is found, "git pull" is probably required'.format(target))
        current_rev = __salt__['git.revision'](target, user=runas)
        if not current_rev:
            return _fail(ret, 'Seems that {0} is not a valid git repo'.format(target))
        if __opts__['test']:
            return _neutral_test(ret, 'Repository {0} upate is probably required (current revision is {1})'.format(target, current_rev))
        if rev:
            __salt__['git.checkout'](target, rev)
        __salt__['git.pull'](target, user=runas)
        new_rev = __salt__['git.revision'](cwd=target, user=runas)
        if current_rev != new_rev:
            log.info('Repository {0} updated: {1} => {2}'.format(target,
                                                                 current_rev,
                                                                 new_rev))
            ret['comment'] = 'Repository {0} updated'.format(target)
            ret['changes']['revision'] = '{0} => {1}'.format(current_rev, new_rev)
    else:
        # git clone is required
        log.debug('target {0} is not found, "git clone" is required'.format(target))
        if __opts__['test']:
            return _neutral_test(ret, 'Repository {0} is about to be cloned to {1}'.format(name, target))
        # make the clone
        result = __salt__['git.clone'](target, name, user=runas)
        if not os.path.isdir(target):
            return _fail(ret, result)
        if rev:
            __salt__['git.checkout'](target, rev)
        else:
            message = 'Repository {0} cloned to {1}'.format(name, target)
            log.info(message)
            ret['comment'] = message
            ret['changes']['new'] = name
    return ret

def _fail(ret, comment):
    ret['result'] = False
    ret['comment'] = comment
    return ret

def _neutral_test(ret, comment):
    ret['result'] = None
    ret['comment'] = comment
    return ret
