'''
Work with cron
'''
import tempfile

def __append_special(user, special, cmd):
    '''
    Append the value to the crontab
    '''
    tmp = tempfile.mkstemp()
    tmpd = open(tmp, 'w+')
    tmpd.write(raw_cron(user))
    tmpd.write(_render_special(special, cmd))
    cmd = 'crontab {0} -u {1}'.format(tmp, user)
    return __salt__['cmd.run'](cmd)

def _render_special(special, cmd):
    '''
    Take a special string and a command string and render it
    '''
    return '{0} {1}'.format(special, cmd)

def raw_cron(user):
    '''
    Return the contents of the user's crontab
    '''
    cmd = 'crontab -l -u {0}'.format(user)
    return __salt__['cmd.run_stdout'](cmd)

def list_tab(user):
    '''
    Return the contents of the specified user's crontab

    CLI Example:
    salt '*' cron.list_tab root
    '''
    data = raw_cron(user)
    ret = {'crons': [],
           'special': []}
    for line in data.split('\n'):
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
        if len(line.split()) > 5:
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
    return ret

def set_special(user, special, cmd):
    '''
    Set up a special command in the crontab.

    CLI Example:
    salt '*' cron.set_special @hourly 'echo foobar'
    '''
    tab = list_tab(user)
    # If the special is set, return True
    for dat in tab['special']:
        if dat['spec'] == special and dat['cmd'] == cmd:
            return True
    return __append_special(user, special, cmd)

