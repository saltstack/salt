'''
Work with cron
'''

# Import python libs
import os
import random

# Import salt libs
import salt.utils


TAG = '# Lines below here are managed by Salt, do not edit\n'


def _needs_change(old, new):
    if old != new:
        if new == 'random':
            # Allow switch from '*' or not present to 'random'
            if old == '*':
                return True
        elif new is not None:
            return True
    return False


def _render_tab(lst):
    '''
    Takes a tab list structure and renders it to a list for applying it to
    a file
    '''
    ret = []
    for pre in lst['pre']:
        ret.append('{0}\n'.format(pre))
    if len(ret):
        if ret[-1] != TAG:
            ret.append(TAG)
    else:
        ret.append(TAG)
    for env in lst['env']:
        if (env['value'] is None) or (env['value'] == ""):
            ret.append('{0}=""\n'.format(env['name']))
        else:
            ret.append('{0}={1}\n'.format(env['name'], env['value']))
    for cron in lst['crons']:
        ret.append('{0} {1} {2} {3} {4} {5}\n'.format(cron['minute'],
                                                      cron['hour'],
                                                      cron['daymonth'],
                                                      cron['month'],
                                                      cron['dayweek'],
                                                      cron['cmd']
                                                      )
                   )
    for spec in lst['special']:
        ret.append('{0} {1}\n'.format(spec['spec'], spec['cmd']))
    return ret


def _get_cron_cmdstr(user, path):
    '''
    Returns a platform-specific format string, to be used to build a crontab
    command.
    '''
    if __grains__['os'] == 'Solaris':
        return 'su - {0} -c "crontab {1}"'.format(user, path)
    else:
        return 'crontab -u {0} {1}'.format(user, path)


def write_cron_file(user, path):
    '''
    Writes the contents of a file to a user's crontab

    CLI Example::

        salt '*' cron.write_cron_file root /tmp/new_cron
    '''
    return __salt__['cmd.retcode'](_get_cron_cmdstr(user, path)) == 0


def write_cron_file_verbose(user, path):
    '''
    Writes the contents of a file to a user's crontab and return error message on error

    CLI Example::

        salt '*' cron.write_cron_file_verbose root /tmp/new_cron
    '''
    return __salt__['cmd.run_all'](_get_cron_cmdstr(user, path))


def _write_cron_lines(user, lines):
    '''
    Takes a list of lines to be committed to a user's crontab and writes it
    '''
    path = salt.utils.mkstemp()
    with salt.utils.fopen(path, 'w+') as fp_:
        fp_.writelines(lines)
    if __grains__['os'] == 'Solaris' and user != "root":
        __salt__['cmd.run']('chown {0} {1}'.format(user, path))
    ret = __salt__['cmd.run_all'](_get_cron_cmdstr(user, path))
    os.remove(path)
    return ret


def _date_time_match(cron, **kwargs):
    '''
    Returns true if the minute, hour, etc. params match their counterparts from
    the dict returned from list_tab().
    '''
    return all([kwargs.get(x) is None or cron[x] == str(kwargs[x])
                or (str(kwargs[x]).lower() == 'random' and cron[x] != '*')
                for x in ('minute', 'hour', 'daymonth', 'month', 'dayweek')])


def raw_cron(user):
    '''
    Return the contents of the user's crontab

    CLI Example::

        salt '*' cron.raw_cron root
    '''
    if __grains__['os'] == 'Solaris':
        cmd = 'crontab -l {0}'.format(user)
    else:
        cmd = 'crontab -l -u {0}'.format(user)
    return __salt__['cmd.run_stdout'](cmd, rstrip=False)


def list_tab(user):
    '''
    Return the contents of the specified user's crontab

    CLI Example::

        salt '*' cron.list_tab root
    '''
    data = raw_cron(user)
    ret = {'pre': [],
           'crons': [],
           'special': [],
           'env': []}
    flag = False
    for line in data.splitlines():
        if line == '# Lines below here are managed by Salt, do not edit':
            flag = True
            continue
        if flag:
            if line.startswith('@'):
                # Its a "special" line
                dat = {}
                comps = line.split()
                if len(comps) < 2:
                    # Invalid line
                    continue
                dat['spec'] = comps[0]
                dat['cmd'] = ' '.join(comps[1:])
                ret['special'].append(dat)
            elif len(line.split()) > 5:
                # Appears to be a standard cron line
                comps = line.split()
                dat = {}
                dat['minute'] = comps[0]
                dat['hour'] = comps[1]
                dat['daymonth'] = comps[2]
                dat['month'] = comps[3]
                dat['dayweek'] = comps[4]
                dat['cmd'] = ' '.join(comps[5:])
                ret['crons'].append(dat)
            elif line.find('=') > 0:
                # Appears to be a ENV setup line
                comps = line.split('=')
                dat = {}
                dat['name'] = comps[0]
                dat['value'] = ' '.join(comps[1:])
                ret['env'].append(dat)
        else:
            ret['pre'].append(line)
    return ret

# For consistency's sake
ls = list_tab  # pylint: disable=C0103


def set_special(user, special, cmd):
    '''
    Set up a special command in the crontab.

    CLI Example::

        salt '*' cron.set_special @hourly 'echo foobar'
    '''
    lst = list_tab(user)
    for cron in lst['special']:
        if special == cron['spec'] and cmd == cron['cmd']:
            return 'present'
    spec = {'spec': special,
            'cmd': cmd}
    lst['special'].append(spec)
    comdat = _write_cron_lines(user, _render_tab(lst))
    if comdat['retcode']:
        # Failed to commit, return the error
        return comdat['stderr']
    return 'new'


def _get_cron_date_time(**kwargs):
    '''
    Returns a dict of date/time values to be used in a cron entry
    '''
    # Define ranges (except daymonth, as it depends on the month)
    range_max = {
        'minute': range(60),
        'hour': range(24),
        'month': range(1, 13),
        'dayweek': range(7)
    }

    ret = {}
    for param in ('minute', 'hour', 'month', 'dayweek'):
        value = str(kwargs.get(param, '1')).lower()
        if value == 'random':
            ret[param] = str(random.sample(range_max[param], 1)[0])
        else:
            ret[param] = value

    if ret['month'] in '1 3 5 7 8 10 12'.split():
        daymonth_max = 31
    elif ret['month'] in '4 6 9 11'.split():
        daymonth_max = 30
    else:
        # This catches both '2' and '*'
        daymonth_max = 28

    daymonth = str(kwargs.get('daymonth', '1')).lower()
    if daymonth == 'random':
        ret['daymonth'] = \
            str(random.sample(range(1, (daymonth_max + 1)), 1)[0])
    else:
        ret['daymonth'] = daymonth

    return ret


def set_job(user, minute, hour, daymonth, month, dayweek, cmd):
    '''
    Sets a cron job up for a specified user.

    CLI Example::

        salt '*' cron.set_job root '*' '*' '*' '*' 1 /usr/local/weekly
    '''
    # Scrub the types
    minute = str(minute).lower()
    hour = str(hour).lower()
    daymonth = str(daymonth).lower()
    month = str(month).lower()
    dayweek = str(dayweek).lower()
    lst = list_tab(user)
    for cron in lst['crons']:
        if cmd == cron['cmd']:
            if any([_needs_change(x, y) for x, y in
                    ((cron['minute'], minute), (cron['hour'], hour),
                     (cron['daymonth'], daymonth), (cron['month'], month),
                     (cron['dayweek'], dayweek))]):
                rm_job(user, cmd)

                # Use old values when setting the new job if there was no
                # change needed for a given parameter
                if not _needs_change(cron['minute'], minute):
                    minute = cron['minute']
                if not _needs_change(cron['hour'], hour):
                    hour = cron['hour']
                if not _needs_change(cron['daymonth'], daymonth):
                    daymonth = cron['daymonth']
                if not _needs_change(cron['month'], month):
                    month = cron['month']
                if not _needs_change(cron['dayweek'], dayweek):
                    dayweek = cron['dayweek']

                jret = set_job(user, minute, hour, daymonth,
                               month, dayweek, cmd)
                if jret == 'new':
                    return 'updated'
                else:
                    return jret
            return 'present'
    cron = {'cmd': cmd}
    cron.update(_get_cron_date_time(minute=minute, hour=hour,
                                    daymonth=daymonth, month=month,
                                    dayweek=dayweek))
    lst['crons'].append(cron)
    comdat = _write_cron_lines(user, _render_tab(lst))
    if comdat['retcode']:
        # Failed to commit, return the error
        return comdat['stderr']
    return 'new'


def rm_job(user,
           cmd,
           minute=None,
           hour=None,
           daymonth=None,
           month=None,
           dayweek=None):
    '''
    Remove a cron job for a specified user. If any of the day/time params are
    specified, the job will only be removed if the specified params match.

    CLI Example::

        salt '*' cron.rm_job root /usr/local/weekly
        salt '*' cron.rm_job root /usr/bin/foo dayweek=1
    '''
    lst = list_tab(user)
    ret = 'absent'
    rm_ = None
    for ind in range(len(lst['crons'])):
        if rm_ is not None:
            break
        if cmd == lst['crons'][ind]['cmd']:
            if not any([x is not None
                        for x in (minute, hour, daymonth, month, dayweek)]):
                # No date/time params were specified
                rm_ = ind
            else:
                if _date_time_match(lst['crons'][ind],
                                    minute=minute,
                                    hour=hour,
                                    daymonth=daymonth,
                                    month=month,
                                    dayweek=dayweek):
                    rm_ = ind
    if rm_ is not None:
        lst['crons'].pop(rm_)
        ret = 'removed'
    comdat = _write_cron_lines(user, _render_tab(lst))
    if comdat['retcode']:
        # Failed to commit, return the error
        return comdat['stderr']
    return ret

rm = rm_job  # pylint: disable=C0103


def set_env(user, name, value=None):
    '''
    Set up an environment variable in the crontab.

    CLI Example::

        salt '*' cron.set_env root MAILTO user@example.com
    '''
    lst = list_tab(user)
    for env in lst['env']:
        if name == env['name']:
            if value != env['value']:
                rm_env(user, name)
                jret = set_env(user, name, value)
                if jret == 'new':
                    return 'updated'
                else:
                    return jret
            return 'present'
    print(value)
    env = {'name': name, 'value': value}
    lst['env'].append(env)
    comdat = _write_cron_lines(user, _render_tab(lst))
    if comdat['retcode']:
        # Failed to commit, return the error
        return comdat['stderr']
    return 'new'


def rm_env(user, name):
    '''
    Remove cron environment variable for a specified user.

    CLI Example::

        salt '*' cron.rm_env root MAILTO
    '''
    lst = list_tab(user)
    ret = 'absent'
    rm_ = None
    for ind in range(len(lst['env'])):
        if name == lst['env'][ind]['name']:
            rm_ = ind
    if rm_ is not None:
        lst['env'].pop(rm_)
        ret = 'removed'
    comdat = _write_cron_lines(user, _render_tab(lst))
    if comdat['retcode']:
        # Failed to commit, return the error
        return comdat['stderr']
    return ret
