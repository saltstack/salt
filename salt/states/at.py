# -*- coding: utf-8 -*-
'''
Configuration disposable regularly scheduled tasks for at.
==========================================================

The at state can be add disposable regularly scheduled tasks for your system.
'''
from __future__ import absolute_import

# Import salt libs
import salt.utils
from salt.ext.six.moves import map

# Tested on OpenBSD 5.0
BSD = ('OpenBSD', 'FreeBSD')


def __virtual__():
    '''
    Most everything has the ability to support at(1)
    '''
    return 'at.at' in __salt__


def present(name, timespec, tag=None, user=None, job=None):
    '''
    Add a job to queue.

    job
        Command to run.

    timespec
        The 'timespec' follows the format documented in the at(1) manpage.

    tag
        Make a tag for the job.

    user
        The user to run the at job

        .. versionadded:: 2014.1.4

    .. code-block:: yaml

        rose:
          at.present:
            - job: 'echo "I love saltstack" > love'
            - timespec: '9:09 11/09/13'
            - tag: love
            - user: jam

    '''
    if job:
        name = job
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'job {0} is add and will run on {1}'.format(name,
                                                                  timespec)}

    binary = salt.utils.which('at')

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'job {0} is add and will run on {1}'.format(name,
                                                                     timespec)
        return ret

    if tag:
        stdin = '### SALT: {0}\n{1}'.format(tag, name)
    else:
        stdin = name
    cmd = '{0} {1}'.format(binary, timespec)

    if user:
        luser = __salt__['user.info'](user)
        if not luser:
            ret['comment'] = 'User: {0} is not exists'.format(user)
            ret['result'] = False
            return ret
        ret['comment'] = __salt__['cmd.run'](cmd, stdin=stdin, runas=user)
    else:
        ret['comment'] = __salt__['cmd.run'](cmd, stdin=stdin)

    return ret


def absent(name, jobid=None, **kwargs):
    '''
    Remove a job from queue
    The 'kwargs' can include hour. minute. day. month. year

    limit
        Target range

    tag
        Job's tag

    runas
        Runs user-specified jobs

    .. code-block:: yaml

        example1:
          at.absent:
            - limit: all

    .. code-block:: yaml

        example2:
          at.absent:
            - limit: all
            - year: 13

    .. code-block:: yaml

        example3:
          at.absent:
            - limit: all
            - tag: rose
            - runas: jim

    .. code-block:: yaml

        example4:
          at.absent:
            - limit: all
            - tag: rose
            - day: 13
            - hour: 16
    '''
    if 'limit' in kwargs:
        name = kwargs['limit']
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    binary = salt.utils.which('at')

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Remove jobs()'
        return ret

    if name != 'all':
        ret['comment'] = 'limit parameter not supported {0}'.format(name)
        ret['result'] = False
        return ret

    #if jobid:
    #    output = __salt__['cmd.run']('{0} -d {1}'.format(binary, jobid))
    #    if i in map(str, [j['job'] for j in __salt__['at.atq']()['jobs']]):
    #        ret['result'] = False
    #        return ret
    #    ret['comment'] = 'Remove job({0}) from queue'.format(' '.join(opts))
    #    return ret

    if kwargs:
        opts = list(list(map(str, [j['job'] for j in __salt__['at.jobcheck'](**kwargs)['jobs']])))
    else:
        opts = list(list(map(str, [j['job'] for j in __salt__['at.atq']()['jobs']])))

    if not opts:
        ret['result'] = False
        ret['comment'] = 'No match jobs or time format error'
        return ret

    __salt__['cmd.run']('{0} -d {1}'.format(binary, ' '.join(opts)))
    fail = []
    for i in opts:
        if i in list(list(map(str, [j['job'] for j in __salt__['at.atq']()['jobs']]))):
            fail.append(i)

    if fail:
        ret['comment'] = 'Remove job({0}) from queue but ({1}) fail'.format(
            ' '.join(opts), fail
       )
    else:
        ret['comment'] = 'Remove job({0}) from queue'.format(' '.join(opts))

    return ret
