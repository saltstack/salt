'''
Wrapper module for at(1)

Also, a 'tag' feature has been added to more
easily tag jobs.
'''

# Import python libs
import re
import time
import datetime

# Import salt libs
import salt.utils

# OS Families that should work (Ubuntu and Debian are the default)
# TODO: Refactor some of this module to remove the checks for binaries

# Tested on OpenBSD 5.0
BSD = ('OpenBSD', 'FreeBSD')


def __virtual__():
    '''
    Most everything has the ability to support at(1)
    '''
    if salt.utils.is_windows() or not salt.utils.which('at'):
        return False
    return 'at'


def _cmd(binary, *args):
    '''
    Wrapper to run at(1) or return None.
    '''
    # TODO: Use CommandNotFoundException for this
    binary = salt.utils.which(binary)
    if binary:
        return __salt__['cmd.run_stdout']('{0} {1}'.format(binary,
            ' '.join(args)))


def atq(tag=None):
    '''
    List all queued and running jobs or only those with
    an optional 'tag'.

    CLI Example::

        salt '*' at.atq
        salt '*' at.atq [tag]
        salt '*' at.atq [job number]
    '''
    jobs = []

    # Shim to produce output similar to what __virtual__() should do
    # but __salt__ isn't available in __virtual__()
    # Tested on CentOS 5.8
    if __grains__['os_family'] == "RedHat":
        output = _cmd('at', '-l')
    else:
        output = _cmd('atq')

    if output is None:
        return '"{0}" is not available.'.format('at.atq')

    # No jobs so return
    if output == '':
        return {'jobs': jobs}

    # Split each job into a dictionary and handle
    # pulling out tags or only listing jobs with a certain
    # tag
    for line in output.splitlines():
        job_tag = ''

        # Jobs created with at.at() will use the following
        # comment to denote a tagged job.
        job_kw_regex = re.compile(r'^### SALT: (\w+)')

        # Redhat/CentOS
        if __grains__['os_family'] == 'RedHat':
            job, spec = line.split('\t')
            specs = spec.split()
        elif __grains__['os'] in BSD:
            if line.startswith(' Rank'):
                continue
            else:
                tmp = line.split()
                timestr = ' '.join(tmp[1:5])
                job = tmp[6]
                specs = datetime.datetime(*(time.strptime(timestr, '%b %d, %Y '
                    '%H:%M')[0:5])).isoformat().split('T')
                specs.append(tmp[7])
                specs.append(tmp[5])

        else:
            job, spec = line.split('\t')
            tmp = spec.split()
            timestr = ' '.join(tmp[0:5])
            specs = datetime.datetime(*(time.strptime(timestr)
                [0:5])).isoformat().split('T')
            specs.append(tmp[5])
            specs.append(tmp[6])

        # Search for any tags
        atc_out = _cmd('at', '-c', job)
        for line in atc_out.splitlines():
            tmp = job_kw_regex.match(line)
            if tmp:
                job_tag = tmp.groups()[0]

        if __grains__['os'] in BSD:
            job = str(job)
        else:
            job = int(job)

        # If a tag is supplied, only list jobs with that tag
        if tag:
            # TODO: Looks like there is a difference between salt and salt-call
            # If I don't wrap job in an int(), it fails on salt but works on
            # salt-call. With the int(), it fails with salt-call but not salt.
            if tag == job_tag or tag == job:
                jobs.append({'job': job, 'date': specs[0], 'time': specs[1],
                    'queue': specs[2], 'user': specs[3], 'tag': job_tag})
        else:
            jobs.append({'job': job, 'date': specs[0], 'time': specs[1],
                'queue': specs[2], 'user': specs[3], 'tag': job_tag})

    return {'jobs': jobs}


def atrm(*args):
    '''
    Remove jobs from the queue.

    CLI Example::

        salt '*' at.atrm <jobid> <jobid> .. <jobid>
        salt '*' at.atrm all
        salt '*' at.atrm all [tag]
    '''

    # Need to do this here also since we use atq()
    if not salt.utils.which('at'):
        return '"{0}" is not available.'.format('at.atrm')

    if not args:
        return {'jobs': {'removed': [], 'tag': None}}

    if args[0] == 'all':
        if len(args) > 1:
            opts = map(str, [j['job'] for j in atq(args[1])['jobs']])
            ret = {'jobs': {'removed': opts, 'tag': args[1]}}
        else:
            opts = map(str, [j['job'] for j in atq()['jobs']])
            ret = {'jobs': {'removed': opts, 'tag': None}}
    else:
        opts = map(str, [i['job'] for i in atq()['jobs']
            if i['job'] in args])
        ret = {'jobs': {'removed': opts, 'tag': None}}

    # Shim to produce output similar to what __virtual__() should do
    # but __salt__ isn't available in __virtual__()
    output = _cmd('at', '-d', ' '.join(opts))
    if output is None:
        return '"{0}" is not available.'.format('at.atrm')

    return ret


def at(*args, **kwargs):  # pylint: disable=C0103
    '''
    Add a job to the queue.

    The 'timespec' follows the format documented in the
    at(1) manpage.

    CLI Example::

        salt '*' at.at <timespec> <cmd> [tag=<tag>] [runas=<user>]
        salt '*' at.at 12:05am '/sbin/reboot' tag=reboot
        salt '*' at.at '3:05am +3 days' 'bin/myscript' tag=nightly runas=jim
    '''

    if len(args) < 2:
        return {'jobs': []}

    # Shim to produce output similar to what __virtual__() should do
    # but __salt__ isn't available in __virtual__()
    binary = salt.utils.which('at')
    if not binary:
        return '"{0}" is not available.'.format('at.at')

    if __grains__['os_family'] == 'RedHat':
        echo_cmd = 'echo -e'
    else:
        echo_cmd = 'echo'

    if 'tag' in kwargs:
        cmd = '{4} "### SALT: {0}\n{1}" | {2} {3}'.format(kwargs['tag'],
            ' '.join(args[1:]), binary, args[0], echo_cmd)
    else:
        cmd = '{3} "{1}" | {2} {0}'.format(args[0], ' '.join(args[1:]),
            binary, echo_cmd)

    # Can't use _cmd here since we need to prepend 'echo_cmd'
    if 'runas' in kwargs:
        output = __salt__['cmd.run']('{0}'.format(cmd), runas=kwargs['runas'])
    else:
        output = __salt__['cmd.run']('{0}'.format(cmd))

    if output is None:
        return '"{0}" is not available.'.format('at.at')

    if output.endswith('Garbled time'):
        return {'jobs': [], 'error': 'invalid timespec'}

    if output.startswith('warning: commands'):
        output = output.splitlines()[1]

    if output.startswith('commands will be executed'):
        output = output.splitlines()[1]

    output = output.split()[1]

    if __grains__['os'] in BSD:
        return atq(str(output))
    else:
        return atq(int(output))


def atc(jobid):
    '''
    Print the at(1) script that will run for the passed job
    id. This is mostly for debugging so the output will
    just be text.

    CLI Example::

        salt '*' at.atc <jobid>
    '''
    # Shim to produce output similar to what __virtual__() should do
    # but __salt__ isn't available in __virtual__()
    output = _cmd('at', '-c', str(jobid))

    if output is None:
        return '"{0}" is not available.'.format('at.atc')
    elif output == '':
        return {'error': 'invalid job id "{0}"'.format(str(jobid))}

    return output

def _formatdate(timespec, delimiter):
    '''
    Return formatted time format: HH:MM YY-mm-dd.
    This is a very simple way, you can extend this method to suit your needs.
    '''

    if ' ' in timespec:
        t = timespec.split()[0]
        d = timespec.split()[1]
        Y = d.split('%s' % delimiter)[2]
        tmp = d.split('%s' % delimiter)

        if len(d.split('%s' % delimiter)[2]) != 4:
            Y = '20' + d.split('%s' % delimiter)[2]
        if delimiter == '/':
            T = "%s %s%s%02d%s%02d" % (t, Y, '-', int(tmp[0]), '-', int(tmp[1]))
        elif delimiter == '.':
            T = "%s %s%s%02d%s%02d" % (t, Y, '-', int(tmp[1]), '-', int(tmp[0]))
    else:
        Y = timespec.split('%s' % delimiter)[2]
        tmp = timespec.split('%s' % delimiter)
        if len(timespec.split('%s' % delimiter)[2]) != 4:
            Y = '20' + timespec.split('%s' % delimiter)[2]
        if delimiter == '/':
            T = "%s%s%02d%s%02d" % (Y, '-', int(tmp[0]), '-', int(tmp[1]))
        elif delimiter == '.':
            T = "%s%s%02d%s%02d" % (Y, '-', int(tmp[1]), '-', int(tmp[0]))
        
    return T

def _atq(**kwargs):
    '''
    Return match jobs list
    '''
    
    jobs = []

    runas = kwargs.get('runas', None)
    time_tag = kwargs.get('timespec', None)
    tag = kwargs.get('tag', None)

    jobinfo = atq()['jobs']
    if not jobinfo:
        return {'jobs': jobs}

    for i in range(0, len(jobinfo)):
        opts = {}
        t = jobinfo[i]['time']
        d = jobinfo[i]['date']
        a = t + ' ' + d
        if runas and time_tag and tag:
            if runas == jobinfo[i]['user']:
                if tag == jobinfo[i]['tag']:
                    if ' ' in time_tag and time_tag == a:
                        opts = jobinfo[i]
                    elif '-' in time_tag and time_tag == d:
                        opts = jobinfo[i]
                    elif ':' in time_tag and time_tag == t:
                        opts = jobinfo[i]
        elif runas and time_tag:
            if runas == jobinfo[i]['user']:
                if ' ' in time_tag and time_tag == a:
                    opts = jobinfo[i]
                elif '-' in time_tag and time_tag == d:
                    opts = jobinfo[i]
                elif ':' in time_tag and time_tag == t:
                    opts = jobinfo[i]
        elif runas and tag:
            if runas == jobinfo[i]['user']:
                if tag == jobinfo[i]['tag']:
                    opts = jobinfo[i]
        elif tag and time_tag:
            if tag == jobinfo[i]['tag']:
                if ' ' in time_tag and time_tag == a:
                    opts = jobinfo[i]
                elif '-' in time_tag and time_tag == d:
                    opts = jobinfo[i]
                elif ':' in time_tag and time_tag == t:
                    opts = jobinfo[i]
        elif runas:
            if runas == jobinfo[i]['user']:
                opts = jobinfo[i]
        elif tag:
            if tag == jobinfo[i]['tag']:
                opts = jobinfo[i]
        elif time_tag:
            if ' ' in time_tag and time_tag == a:
                opts = jobinfo[i]
            elif '-' in time_tag and time_tag == d:
                opts = jobinfo[i]
            elif ':' in time_tag and time_tag == t:
                opts = jobinfo[i]

        if opts:
            jobs.append(opts)

    if not jobs:
        note = 'No match jobs'
        return {'jobs': jobs, 'note': note}

    return {'jobs': jobs}

def jobcheck(**kwargs):  # pylint: disable=C0103
    '''
    According to the given parameters match the return queue job list
    '''

    if not kwargs:
        return {'error': 'You have given a condition'}

    if "timespec" in kwargs.keys():
        time_spec = kwargs['timespec']

        _t = '((00|[0][1-9]|[1][0-9]|[2][0-3]):[0-5][0-9])$'
        mdy = '(([0]?[13578]|10|12)/([0]?[1-9]|[1-2][0-9]|30|31)|([0]?[469]|11)/([0]?[1-9]|[1-2][0-9]|30)|([0]?[2])/([0]?[1-9]|[1-2][0-9]))/(\d{2}|\d{4})$'    # MM/DD/YY
        dmy = '(([0]?[1-9]|[1-2][0-9]|30|31)\.([0]?[13578]|10|12)|([0]?[1-9]|[1-2][0-9]|30)\.([0]?[469]|11)|([0]?[1-9]|[1-2][0-9])\.[0]?[2])\.(\d{2}|\d{4})$'    # DD.MM.YY
        ymd = '(\d{2}|\d{4})-(([0][13578]|10|12)-([0][1-9]|[1-2][0-9]|30|31)|([0]?469]|11)-([0][1-9]|[1-2]|[0-9]|30)|([0][2])-([0][1-9]|[1-2][0-9]))$'    # YY-MM-DD
        only_time = re.compile(r'%s' % _t)
        only_mdy = re.compile(r'%s' % mdy)
        only_dmy = re.compile(r'%s' % dmy)
        only_ymd = re.compile(r'%s' % ymd)
        time_mdy = re.compile(r'%s %s' % (_t[:-1], mdy))
        time_dmy = re.compile(r'%s %s' % (_t[:-1], dmy))
        time_ymd = re.compile(r'%s %s' % (_t[:-1], ymd))

        # Greater than 599 minutes Format Convertor
        try:
            if int(time_spec) > 599:
                time_spec = "%02d:%02d" % (int(time_spec)/60, int(time_spec)%60)
        except:
            pass

        if only_time.match(time_spec):
            # 17:25
            time_tag = only_time.match(time_spec).group(0)
        elif only_ymd.match(time_spec):
            # 2013-11-30
            time_tag = only_ymd.match(time_spec).group(0)
        elif only_mdy.match(time_spec):
            # 11/30/2013
            hit = only_mdy.match(time_spec).group(0)
            time_tag = _formatdate(hit, '/')
        elif only_dmy.match(time_spec):
            # 30.11.2013
            hit = only_dmy.match(time_spec).group(0)
            time_tag = _formatdate(hit, '.')
        elif time_mdy.match(time_spec):
            # 17:25 11/29/13
            hit = time_mdy.match(time_spec).group(0)
            time_tag = _formatdate(hit, '/')
        elif time_dmy.match(time_spec):
            # 17:25 29.11.13
            hit = time_dmy.match(time_spec).group(0)
            time_tag = _formatdate(hit, '.')
        elif time_ymd.match(time_spec):
            # 17:25 2013-11-13
            time_tag = time_ymd.match(time_spec).group(0)
        else:
            return {'error': 'Sorry,this time format is not supported'}
        kwargs.update(timespec=time_tag)

    return _atq(**kwargs)
