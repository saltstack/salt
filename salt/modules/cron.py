'''
Work with cron
'''

# Import python libs
import os

# Import salt libs
import salt.utils


TAG = '# Lines below here are managed by Salt, do not edit\n'


def _render_tab(lst):
    '''
    Takes a tab list structure and renders it to a list for applying it to
    a file
    '''
    ret = []
    for pre in lst['pre']:
        ret.append('{0}\n'.format(pre))
    if len(ret):
        if not ret[-1] == TAG:
            ret.append(TAG)
    else:
        ret.append(TAG)
    for env in lst['env']:
        if (env['value'] is None) or (env['value'] == ""):
            ret.append('{0}=""\n'.format(env['name']))
        else:
            ret.append('{0}={1}\n'.format(env['name'], env['value']))
    for cron in lst['crons']:
        ret.append('{0} {1} {2} {3} {4} {5}\n'.format(cron['min'],
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
                dat['min'] = comps[0]
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
ls = list_tab  # pylint: disable-msg=C0103


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


def set_job(user, minute, hour, dom, month, dow, cmd):
    '''
    Sets a cron job up for a specified user.

    CLI Example::

        salt '*' cron.set_job root \* \* \* \* 1 /usr/local/weekly
    '''
    # Scrub the types
    minute = str(minute)
    hour = str(hour)
    dom = str(dom)
    month = str(month)
    dow = str(dow)
    lst = list_tab(user)
    for cron in lst['crons']:
        if cmd == cron['cmd']:
            if not minute == cron['min'] or \
                    not hour == cron['hour'] or \
                    not dom == cron['daymonth'] or \
                    not month == cron['month'] or \
                    not dow == cron['dayweek']:
                rm_job(user, minute, hour, dom, month, dow, cmd)
                jret = set_job(user, minute, hour, dom, month, dow, cmd)
                if jret == 'new':
                    return 'updated'
                else:
                    return jret
            return 'present'
    cron = {'min': minute,
            'hour': hour,
            'daymonth': dom,
            'month': month,
            'dayweek': dow,
            'cmd': cmd}
    lst['crons'].append(cron)
    comdat = _write_cron_lines(user, _render_tab(lst))
    if comdat['retcode']:
        # Failed to commit, return the error
        return comdat['stderr']
    return 'new'


def rm_job(user, minute, hour, dom, month, dow, cmd):
    '''
    Remove a cron job for a specified user.

    CLI Example::

        salt '*' cron.rm_job root \* \* \* \* 1 /usr/local/weekly
    '''
    lst = list_tab(user)
    ret = 'absent'
    rm_ = None
    for ind in range(len(lst['crons'])):
        if cmd == lst['crons'][ind]['cmd']:
            rm_ = ind
    if rm_ is not None:
        lst['crons'].pop(rm_)
        ret = 'removed'
    comdat = _write_cron_lines(user, _render_tab(lst))
    if comdat['retcode']:
        # Failed to commit, return the error
        return comdat['stderr']
    return ret

rm = rm_job  # pylint: disable-msg=C0103


def set_env(user, name, value=None):
    '''
    Set up an environment variable in the crontab.

    CLI Example::

        salt '*' cron.set_env root MAILTO user@example.com
    '''
    lst = list_tab(user)
    for env in lst['env']:
        if name == env['name']:
            if not value == env['value']:
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
