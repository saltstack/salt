# -*- coding: utf-8 -*-
'''
The return data from the Highstate command is a standard data structure
which is parsed by the highstate outputter to deliver a clean and readable
set of information about the HighState run on minions.

Two configurations can be set to modify the highstate outputter. These values
can be set in the master config to change the output of the ``salt`` command or
set in the minion config to change the output of the ``salt-call`` command.

state_verbose:
    By default `state_verbose` is set to `True`, setting this to `False` will
    instruct the highstate outputter to omit displaying anything in green, this
    means that nothing with a result of True and no changes will not be printed
state_output:
    The highstate outputter has three output modes, `full`, `terse`, `mixed`,
    and `changes`. The default is set to full, which will display many lines of
    detailed information for each executed chunk. If the `state_output` option
    is set to `terse` then the output is greatly simplified and shown in only
    one line.  If `mixed` is used, then terse output will be used unless a
    state failed, in which case full output will be used.  If `changes` is used,
    then terse output will be used if there was no error and no changes,
    otherwise full output will be used.
state_tabular:
    If `state_output` uses the terse output, set this to `True` for an aligned
    output format.  If you wish to use a custom format, this can be set to a
    string.
'''

# Import python libs
import pprint

# Import salt libs
import salt.utils


def output(data):
    '''
    The HighState Outputter is only meant to
    be used with the state.highstate function, or a function that returns
    highstate return data.
    '''
    colors = salt.utils.get_colors(__opts__.get('color'))
    tabular = __opts__.get('state_tabular', False)
    for host in data:
        rcounts = {}
        hcolor = colors['GREEN']
        hstrs = []
        if isinstance(data[host], list):
            # Errors have been detected, list them in RED!
            hcolor = colors['RED_BOLD']
            hstrs.append(('    {0}Data failed to compile:{1[ENDC]}'
                          .format(hcolor, colors)))
            for err in data[host]:
                hstrs.append(('{0}----------\n    {1}{2[ENDC]}'
                              .format(hcolor, err, colors)))
        if isinstance(data[host], dict):
            # Strip out the result: True, without changes returns if
            # state_verbose is False
            if not __opts__.get('state_verbose', False):
                data[host] = _strip_clean(data[host])
            # Verify that the needed data is present
            for tname, info in data[host].items():
                if not '__run_num__' in info:
                    err = ('The State execution failed to record the order '
                           'in which all states were executed. The state '
                           'return missing data is:')
                    hstrs.insert(0, pprint.pformat(info))
                    hstrs.insert(0, err)
            # Everything rendered as it should display the output
            for tname in sorted(
                    data[host],
                    key=lambda k: data[host][k].get('__run_num__', 0)):
                ret = data[host][tname]
                # Increment result counts
                rcounts.setdefault(ret['result'], 0)
                rcounts[ret['result']] += 1
                tcolor = colors['GREEN']
                if ret['changes']:
                    tcolor = colors['CYAN']
                if ret['result'] is False:
                    hcolor = colors['RED']
                    tcolor = colors['RED']
                if ret['result'] is None:
                    hcolor = colors['YELLOW']
                    tcolor = colors['YELLOW']
                comps = tname.split('_|-')
                if __opts__.get('state_output', 'full').lower() == 'terse':
                    # Print this chunk in a terse way and continue in the
                    # loop
                    msg = _format_terse(tcolor, comps, ret, colors, tabular)
                    hstrs.append(msg)
                    continue
                elif __opts__.get('state_output', 'full').lower() == 'mixed':
                    # Print terse unless it failed
                    if ret['result'] is not False:
                        msg = _format_terse(tcolor, comps, ret, colors, tabular)
                        hstrs.append(msg)
                        continue
                elif __opts__.get('state_output', 'full').lower() == 'changes':
                    # Print terse if no error and no changes, otherwise, be
                    # verbose
                    if ret['result'] and not ret['changes']:
                        msg = _format_terse(tcolor, comps, ret, colors, tabular)
                        hstrs.append(msg)
                        continue
                state_lines = [
                    '{tcolor}----------{colors[ENDC]}',
                    '    {tcolor}      ID: {comps[1]}{colors[ENDC]}',
                    '    {tcolor}Function: {comps[0]}.{comps[3]}{colors[ENDC]}',
                    '    {tcolor}  Result: {ret[result]!s}{colors[ENDC]}',
                    '    {tcolor} Comment: {comment}{colors[ENDC]}'
                ]
                # This isn't the prettiest way of doing this, but it's readable.
                if (comps[1] != comps[2]):
                    state_lines.insert(
                        3, '    {tcolor}    Name: {comps[2]}{colors[ENDC]}')
                svars = {
                    'tcolor': tcolor,
                    'comps': comps,
                    'ret': ret,
                    # This nukes any trailing \n and indents the others.
                    'comment': ret['comment'].strip().replace(
                        '\n',
                        '\n' + ' ' * 14),
                    'colors': colors
                }
                hstrs.extend([sline.format(**svars) for sline in state_lines])
                changes = '     Changes:   '
                if not isinstance(ret['changes'], dict):
                    changes += 'Invalid Changes data: {0}'.format(
                            ret['changes'])
                else:
                    pass_opts = __opts__
                    if __opts__['color']:
                        pass_opts['color'] = 'CYAN'
                    pass_opts['nested_indent'] = 14
                    changes += '\n'
                    changes += salt.output.out_format(
                            ret['changes'],
                            'nested',
                            pass_opts)
                hstrs.append(('{0}{1}{2[ENDC]}'
                              .format(tcolor, changes, colors)))

            # Append result counts to end of output
            colorfmt = '{0}{1}{2[ENDC]}'
            rlabel = {True: 'Succeeded', False: 'Failed', None: 'Not Run'}
            count_max_len = max([len(str(x)) for x in rcounts.values()] or [0])
            label_max_len = max([len(x) for x in rlabel.values()] or [0])
            line_max_len = label_max_len + count_max_len + 2  # +2 for ': '
            hstrs.append(
                colorfmt.format(
                    colors['CYAN'],
                    '\nSummary\n{0}'.format('-' * line_max_len),
                    colors
                )
            )

            def _counts(label, count):
                return '{0}: {1:>{2}}'.format(
                    label,
                    count,
                    line_max_len - (len(label) + 2)
                )

            # Successful states
            hstrs.append(
                colorfmt.format(
                    colors['GREEN'],
                    _counts(rlabel[True], rcounts.get(True, 0)),
                    colors
                )
            )

            # Failed states
            num_failed = rcounts.get(False, 0)
            hstrs.append(
                colorfmt.format(
                    colors['RED'] if num_failed else colors['CYAN'],
                    _counts(rlabel[False], num_failed),
                    colors
                )
            )

            # test=True states
            if None in rcounts:
                hstrs.append(
                    colorfmt.format(
                        colors['YELLOW'],
                        _counts(rlabel[None], rcounts.get(None, 0)),
                        colors
                    )
                )

            totals = '{0}\nTotal: {1:>{2}}'.format('-' * line_max_len,
                                                   sum(rcounts.values()),
                                                   line_max_len - 7)
            hstrs.append(colorfmt.format(colors['CYAN'], totals, colors))

        hstrs.insert(0, ('{0}{1}:{2[ENDC]}'.format(hcolor, host, colors)))
        return '\n'.join(hstrs)


def _strip_clean(returns):
    '''
    Check for the state_verbose option and strip out the result=True
    and changes={} members of the state return list.
    '''
    rm_tags = []
    for tag in returns:
        if returns[tag]['result'] and not returns[tag]['changes']:
            rm_tags.append(tag)
    for tag in rm_tags:
        returns.pop(tag)
    return returns


def _format_terse(tcolor, comps, ret, colors, tabular):
    '''
    Terse formatting of a message.
    '''
    result = "Clean"
    if ret['changes']:
        result = "Changed"
    if ret['result'] is False:
        result = "Failed"
    elif ret['result'] is None:
        result = "Differs"
    if tabular is True:
        fmt_string = '{0}{2:>10}.{3:<10} {4:7}   Name: {1}{5}'
    elif isinstance(tabular, str):
        fmt_string = tabular
    else:
        fmt_string = ' {0} Name: {1} - Function: {2}.{3} - Result: {4}{5}'
    msg = fmt_string.format(tcolor,
                            comps[2],
                            comps[0],
                            comps[-1],
                            result,
                            colors['ENDC'],
                            ret)

    return msg
