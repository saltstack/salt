# -*- coding: utf-8 -*-
'''
Configuration disposable regularly scheduled tasks for at.
==========================================================

The at state can be add disposable regularly scheduled tasks for your system.
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
import logging

# Import salt libs
from salt.ext.six.moves import map

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Most everything has the ability to support at(1)
    '''
    return 'at.at' in __salt__


def present(name, timespec, tag=None, user=None, job=None, unique_tag=False):
    '''
    .. versionchanged:: 2017.7.0
    Add a job to queue.

    job : string
        Command to run.

    timespec : string
        The 'timespec' follows the format documented in the at(1) manpage.

    tag : string
        Make a tag for the job.

    user : string
        The user to run the at job
        .. versionadded:: 2014.1.4

    unique_tag : boolean
        If set to True job will not be added if a job with the tag exists.
        .. versionadded:: 2017.7.0

    .. code-block:: yaml

        rose:
          at.present:
            - job: 'echo "I love saltstack" > love'
            - timespec: '9:09 11/09/13'
            - tag: love
            - user: jam

    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    # if job is missing, use name
    if not job:
        job = name

    # quick return on test=True
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'job {0} added and will run on {1}'.format(
            job,
            timespec,
        )
        return ret

    # quick return if unique_tag and job exists
    if unique_tag:
        if not tag:
            ret['result'] = False
            ret['comment'] = 'no tag provided and unique_tag is set to True'
            return ret
        elif len(__salt__['at.jobcheck'](tag=tag)['jobs']) > 0:
            ret['comment'] = 'atleast one job with tag {tag} exists.'.format(
                tag=tag
            )
            return ret

    # create job
    if user:
        luser = __salt__['user.info'](user)
        if not luser:
            ret['result'] = False
            ret['comment'] = 'user {0} does not exists'.format(user)
            return ret
        ret['comment'] = 'job {0} added and will run as {1} on {2}'.format(
            job,
            user,
            timespec,
        )
        res = __salt__['at.at'](
            timespec,
            job,
            tag=tag,
            runas=user,
        )
    else:
        ret['comment'] = 'job {0} added and will run on {1}'.format(
            job,
            timespec,
        )
        res = __salt__['at.at'](
            timespec,
            job,
            tag=tag,
        )

    # set ret['changes']
    if 'jobs' in res and len(res['jobs']) > 0:
        ret['changes'] = res['jobs'][0]
    if 'error' in res:
        ret['result'] = False
        ret['comment'] = res['error']

    return ret


def absent(name, jobid=None, **kwargs):
    '''
    .. versionchanged:: 2017.7.0
    Remove a job from queue

    jobid: string|int
        Specific jobid to remove

    tag : string
        Job's tag

    runas : string
        Runs user-specified jobs

    **kwags : *
        Addition kwargs can be provided to filter jobs.
        See output of `at.jobcheck` for more.

    .. code-block:: yaml

        example1:
          at.absent:

    .. warning::
        this will remove all jobs!

    .. code-block:: yaml

        example2:
          at.absent:
            - year: 13

    .. code-block:: yaml

        example3:
          at.absent:
            - tag: rose

    .. code-block:: yaml

        example4:
          at.absent:
            - tag: rose
            - day: 13
            - hour: 16

    .. code-block:: yaml

        example5:
          at.absent:
            - jobid: 4

    .. note:
        all other filters are ignored and only job with id 4 is removed
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    # limit was never support
    if 'limit' in kwargs:
        ret['comment'] = 'limit parameter not supported {0}'.format(name)
        ret['result'] = False
        return ret

    # quick return on test=True
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'removed ? job(s)'
        return ret

    # remove specific job
    if jobid:
        jobs = __salt__['at.atq'](jobid)
        if 'jobs' in jobs and len(jobs['jobs']) == 0:
            ret['result'] = True
            ret['comment'] = 'job with id {jobid} not present'.format(
                jobid=jobid
            )
            return ret
        elif 'jobs' in jobs and len(jobs['jobs']) == 1:
            if 'job' in jobs['jobs'][0] and jobs['jobs'][0]['job']:
                res = __salt__['at.atrm'](jobid)
                ret['result'] = jobid in res['jobs']['removed']
                if ret['result']:
                    ret['comment'] = 'job with id {jobid} was removed'.format(
                        jobid=jobid
                    )
                else:
                    ret['comment'] = 'failed to remove job with id {jobid}'.format(
                        jobid=jobid
                    )
                ret['changes']['removed'] = res['jobs']['removed']
                return ret
        else:
            ret['result'] = False
            ret['comment'] = 'more than one job was return for job with id {jobid}'.format(
                jobid=jobid
            )
            return ret

    # remove jobs based on filter
    if kwargs:
        # we pass kwargs to at.jobcheck
        opts = list(list(map(str, [j['job'] for j in __salt__['at.jobcheck'](**kwargs)['jobs']])))
        res = __salt__['at.atrm'](*opts)
    else:
        # arguments to filter with, removing everything!
        res = __salt__['at.atrm']('all')

    if len(res['jobs']['removed']) > 0:
        ret['changes']['removed'] = res['jobs']['removed']
    ret['comment'] = 'removed {count} job(s)'.format(
        count=len(res['jobs']['removed'])
    )
    return ret


def watch(name, timespec, tag=None, user=None, job=None, unique_tag=False):
    '''
    .. versionadded:: 2017.7.0
    Add an at job if trigger by watch

    job : string
        Command to run.

    timespec : string
        The 'timespec' follows the format documented in the at(1) manpage.

    tag : string
        Make a tag for the job.

    user : string
        The user to run the at job
        .. versionadded:: 2014.1.4

    unique_tag : boolean
        If set to True job will not be added if a job with the tag exists.
        .. versionadded:: 2017.7.0

    .. code-block:: yaml

        minion_restart:
          at.watch:
            - job: 'salt-call --local service.restart salt-minion'
            - timespec: 'now +1 min'
            - tag: minion_restart
            - unique_tag: trye
            - watch:
                - file: /etc/salt/minion

    '''
    return {
        'name': name,
        'changes': {},
        'result': True,
        'comment': ''
    }


def mod_watch(name, **kwargs):
    '''
    The at watcher, called to invoke the watch command.

    name
        The name of the atjob

    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if kwargs['sfun'] == 'watch':
        for p in ['sfun', '__reqs__']:
            del kwargs[p]
        kwargs['name'] = name
        ret = present(**kwargs)

    return ret


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
