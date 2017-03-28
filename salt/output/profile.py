
__virtualname__ = 'profile'
tabulate = None

def __virtual__():
    try:
        global tabulate
        from tabulate import tabulate
        return True
    except:
        return False

def _find_durations(data, name_max=60):
    ret = []
    for host in data:
        for sid in data[host]:
            dat  = data[host][sid]
            ts   = sid.split('_|-')
            mod  = ts[0]
            fun  = ts[-1]
            name = dat.get('name', dat.get('__id__'))
            dur  = float(data[host][sid].get('duration',-1))

            if name is None:
                name = '<>'
            if len(name) > name_max:
                name = name[0:name_max-3] + '...'

            ret.append( [dur, name, '{0}.{1}'.format(mod,fun)] )
    return [ x[1:] + x[0:1] for x in sorted(ret) ]

def output(data):
    '''
    Attempt to output the returns of state.sls and state.highstate as a table of
    names, modules and durations that looks somewhat like the following:

        name                mod.fun                duration (ms)
        ------------------  -------------------  ---------------
        I-fail-unless-stmt  other.function                -1
        old-minion-config   grains.list_present            1.12
        salt-data           group.present                 48.38
        /etc/salt/minion    file.managed                  63.145

    In order for this outputter to be available, the tabulate module must be
    installed and available.

    '''
    rows = _find_durations(data)
    return tabulate(rows, headers=['name', 'mod.fun', 'duration (ms)'], tablefmt='postgres' )
