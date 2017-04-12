
import table_out

__virtualname__ = 'profile'

def __virtual__():
    return True

def _find_durations(data, name_max=60):
    ret = []
    ml = len('duration (ms)')
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

            l = len('{0:0.4f}'.format(dur))
            if l > ml:
                ml = l

            ret.append( [dur, name, '{0}.{1}'.format(mod,fun)] )

    for row in ret:
        row[0] = '{0:{w}.4f}'.format(row[0], w=ml)
    return [ x[1:] + x[0:1] for x in sorted(ret) ]

def output(data, **kwargs):
    '''

    Show profile data for returners that would normally show a highstate output.

        salt globhere state.sls something --out=profile

    Attempt to output the returns of state.sls and state.highstate as a table of
    names, modules and durations that looks somewhat like the following:

        name                mod.fun                duration (ms)
        --------------------------------------------------------
        I-fail-unless-stmt  other.function               -1.0000
        old-minion-config   grains.list_present           1.1200
        salt-data           group.present                48.3800
        /etc/salt/minion    file.managed                 63.1450


    To get the above appearance, use settings something like these:
      out.table.separate_rows: False
      out.table.justify: left
      out.table.delim: '  '
      out.table.prefix: ''
      out.table.suffix: ''
    '''

    rows = _find_durations(data)

    kwargs['opts'] = __opts__
    kwargs['rows_key'] = 'rows'
    kwargs['labels_key'] = 'labels'

    to_show = {'labels': ['name', 'mod.fun', 'duration (ms)'],
               'rows':   rows }

    return table_out.output(to_show, **kwargs)
