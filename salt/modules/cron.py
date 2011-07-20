'''
Work with cron
'''

def list_tab(user):
    '''
    Return the contents of the specified user's crontab

    CLI Example:
    salt '*' cron.list_tab root
    '''
    cmd = 'crontab -l -u {0}'.format(user)
    ret = {'crons': [],
           'special': []}
    data = __salt__['cmd.run_stdout'](cmd)
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
