# -*- coding: utf-8 -*-
'''
Outputter for displaying results of state runs
==============================================

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
    The highstate outputter has five output modes, `full`, `terse`, `mixed`,
    `changes` and `filter`. The default is set to full, which will display many
    lines of detailed information for each executed chunk. If the `state_output`
    option is set to `terse` then the output is greatly simplified and shown in
    only one line.  If `mixed` is used, then terse output will be used unless a
    state failed, in which case full output will be used.  If `changes` is used,
    then terse output will be used if there was no error and no changes,
    otherwise full output will be used. If `filter` is used, then either or both
    of two different filters can be used: `exclude` or `terse`. These can be set
    as such from the command line, or in the Salt config as
    `state_output_exclude` or `state_output_terse`, respectively. The values to
    exclude must be a comma-separated list of `True`, `False` and/or `None`.
    Because of parsing nuances, if only one of these is used, it must still
    contain a comma. For instance: `exclude=True,`.
state_tabular:
    If `state_output` uses the terse output, set this to `True` for an aligned
    output format.  If you wish to use a custom format, this can be set to a
    string.

Example output:

.. code-block:: text

    myminion:
    ----------
              ID: test.ping
        Function: module.run
          Result: True
         Comment: Module function test.ping executed
         Changes:
                  ----------
                  ret:
                      True

    Summary
    ------------
    Succeeded: 1
    Failed:    0
    ------------
    Total:     0
'''


# Import python libs
from __future__ import absolute_import
import pprint
import textwrap

# Import salt libs
import salt.utils
import salt.output
import salt.ext.six as six
from salt.ext.six import string_types


def output(data):
    '''
    The HighState Outputter is only meant to be used with the state.highstate
    function, or a function that returns highstate return data.
    '''
    for host, hostdata in six.iteritems(data):
        return _format_host(host, hostdata)[0]


def _format_host(host, data):
    colors = salt.utils.get_colors(__opts__.get('color'))
    tabular = __opts__.get('state_tabular', False)
    rcounts = {}
    hcolor = colors['GREEN']
    hstrs = []
    nchanges = 0
    strip_colors = __opts__.get('strip_colors', True)

    if isinstance(data, int) or isinstance(data, str):
        # Data in this format is from saltmod.function,
        # so it is always a 'change'
        nchanges = 1
        hstrs.append((u'{0}    {1}{2[ENDC]}'
                      .format(hcolor, data, colors)))
        hcolor = colors['CYAN']  # Print the minion name in cyan
    if isinstance(data, list):
        # Errors have been detected, list them in RED!
        hcolor = colors['RED_BOLD']
        hstrs.append((u'    {0}Data failed to compile:{1[ENDC]}'
                      .format(hcolor, colors)))
        for err in data:
            if strip_colors:
                err = salt.output.strip_esc_sequence(err)
            hstrs.append((u'{0}----------\n    {1}{2[ENDC]}'
                          .format(hcolor, err, colors)))
    if isinstance(data, dict):
        # Strip out the result: True, without changes returns if
        # state_verbose is False
        if not __opts__.get('state_verbose', False):
            data = _strip_clean(data)
        # Verify that the needed data is present
        for tname, info in data.items():
            if isinstance(info, dict) and '__run_num__' not in info:
                err = (u'The State execution failed to record the order '
                       'in which all states were executed. The state '
                       'return missing data is:')
                hstrs.insert(0, pprint.pformat(info))
                hstrs.insert(0, err)
        # Everything rendered as it should display the output
        for tname in sorted(
                data,
                key=lambda k: data[k].get('__run_num__', 0)):
            ret = data[tname]
            # Increment result counts
            rcounts.setdefault(ret['result'], 0)
            rcounts[ret['result']] += 1

            tcolor = colors['GREEN']
            schanged, ctext = _format_changes(ret['changes'])
            nchanges += 1 if schanged else 0

            # Skip this state if it was successful & diff output was requested
            if __opts__.get('state_output_diff', False) and \
               ret['result'] and not schanged:
                continue

            if schanged:
                tcolor = colors['CYAN']
            if ret['result'] is False:
                hcolor = colors['RED']
                tcolor = colors['RED']
            if ret['result'] is None:
                hcolor = colors['YELLOW']
                tcolor = colors['YELLOW']
            comps = tname.split('_|-')
            if __opts__.get('state_output', 'full').lower() == 'filter':
                # By default, full data is shown for all types. However, return
                # data may be excluded by setting state_output_exclude to a
                # comma-separated list of True, False or None, or including the
                # same list with the exclude option on the command line. For
                # now, this option must include a comma. For example:
                #     exclude=True,
                # The same functionality is also available for making return
                # data terse, instead of excluding it.
                cliargs = __opts__.get('arg', [])
                clikwargs = {}
                for item in cliargs:
                    if isinstance(item, dict) and '__kwarg__' in item:
                        clikwargs = item.copy()

                exclude = clikwargs.get(
                    'exclude', __opts__.get('state_output_exclude', [])
                )
                if isinstance(exclude, string_types):
                    exclude = str(exclude).split(',')

                terse = clikwargs.get(
                    'terse', __opts__.get('state_output_terse', [])
                )
                if isinstance(terse, string_types):
                    terse = str(terse).split(',')

                if str(ret['result']) in terse:
                    msg = _format_terse(tcolor, comps, ret, colors, tabular)
                    hstrs.append(msg)
                    continue
                if str(ret['result']) in exclude:
                    continue
            elif __opts__.get('state_output', 'full').lower() == 'terse':
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
                if ret['result'] and not schanged:
                    msg = _format_terse(tcolor, comps, ret, colors, tabular)
                    hstrs.append(msg)
                    continue
            state_lines = [
                u'{tcolor}----------{colors[ENDC]}',
                u'    {tcolor}      ID: {comps[1]}{colors[ENDC]}',
                u'    {tcolor}Function: {comps[0]}.{comps[3]}{colors[ENDC]}',
                u'    {tcolor}  Result: {ret[result]!s}{colors[ENDC]}',
                u'    {tcolor} Comment: {comment}{colors[ENDC]}',
                u'    {tcolor} Started: {ret[start_time]!s}{colors[ENDC]}',
                u'    {tcolor}Duration: {ret[duration]!s}{colors[ENDC]}'
            ]
            # This isn't the prettiest way of doing this, but it's readable.
            if comps[1] != comps[2]:
                state_lines.insert(
                    3, u'    {tcolor}    Name: {comps[2]}{colors[ENDC]}')
            # be sure that ret['comment'] is utf-8 friendly
            try:
                if not isinstance(ret['comment'], six.text_type):
                    ret['comment'] = ret['comment'].decode('utf-8')
            except UnicodeDecodeError:
                # but try to continue on errors
                pass
            try:
                comment = salt.utils.sdecode(ret['comment'])
                comment = comment.strip().replace(
                        u'\n',
                        u'\n' + u' ' * 14)
            except AttributeError:  # Assume comment is a list
                try:
                    comment = ret['comment'].join(' ').replace(
                        u'\n',
                        u'\n' + u' ' * 13)
                except AttributeError:
                    # Comment isn't a list either, just convert to string
                    comment = str(ret['comment'])
                    comment = comment.strip().replace(
                        u'\n',
                        u'\n' + u' ' * 14)
            for detail in ['start_time', 'duration']:
                ret.setdefault(detail, u'')
            if ret['duration'] != '':
                ret['duration'] = u'{0} ms'.format(ret['duration'])
            svars = {
                'tcolor': tcolor,
                'comps': comps,
                'ret': ret,
                'comment': comment,
                # This nukes any trailing \n and indents the others.
                'colors': colors
            }
            hstrs.extend([sline.format(**svars) for sline in state_lines])
            changes = u'     Changes:   ' + ctext
            hstrs.append((u'{0}{1}{2[ENDC]}'
                          .format(tcolor, changes, colors)))

            if 'warnings' in ret:
                rcounts.setdefault('warnings', 0)
                rcounts['warnings'] += 1
                wrapper = textwrap.TextWrapper(
                    width=80,
                    initial_indent=u' ' * 14,
                    subsequent_indent=u' ' * 14
                )
                hstrs.append(
                    u'   {colors[LIGHT_RED]} Warnings: {0}{colors[ENDC]}'.format(
                        wrapper.fill('\n'.join(ret['warnings'])).lstrip(),
                        colors=colors
                    )
                )

        # Append result counts to end of output
        colorfmt = u'{0}{1}{2[ENDC]}'
        rlabel = {True: u'Succeeded', False: u'Failed', None: u'Not Run', 'warnings': u'Warnings'}
        count_max_len = max([len(str(x)) for x in six.itervalues(rcounts)] or [0])
        label_max_len = max([len(x) for x in six.itervalues(rlabel)] or [0])
        line_max_len = label_max_len + count_max_len + 2  # +2 for ': '
        hstrs.append(
            colorfmt.format(
                colors['CYAN'],
                u'\nSummary\n{0}'.format('-' * line_max_len),
                colors
            )
        )

        def _counts(label, count):
            return u'{0}: {1:>{2}}'.format(
                label,
                count,
                line_max_len - (len(label) + 2)
            )

        # Successful states
        changestats = []
        if None in rcounts and rcounts.get(None, 0) > 0:
            # test=True states
            changestats.append(
                colorfmt.format(
                    colors['YELLOW'],
                    u'unchanged={0}'.format(rcounts.get(None, 0)),
                    colors
                )
            )
        if nchanges > 0:
            changestats.append(
                colorfmt.format(
                    colors['GREEN'],
                    u'changed={0}'.format(nchanges),
                    colors
                )
            )
        if changestats:
            changestats = u' ({0})'.format(', '.join(changestats))
        else:
            changestats = u''
        hstrs.append(
            colorfmt.format(
                colors['GREEN'],
                _counts(
                    rlabel[True],
                    rcounts.get(True, 0) + rcounts.get(None, 0)
                ),
                colors
            ) + changestats
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

        num_warnings = rcounts.get('warnings', 0)
        if num_warnings:
            hstrs.append(
                colorfmt.format(
                    colors['LIGHT_RED'],
                    _counts(rlabel['warnings'], num_warnings),
                    colors
                )
            )

        totals = u'{0}\nTotal states run: {1:>{2}}'.format('-' * line_max_len,
                                               sum(six.itervalues(rcounts)) - rcounts.get('warnings', 0),
                                               line_max_len - 7)
        hstrs.append(colorfmt.format(colors['CYAN'], totals, colors))

    if strip_colors:
        host = salt.output.strip_esc_sequence(host)
    hstrs.insert(0, (u'{0}{1}:{2[ENDC]}'.format(hcolor, host, colors)))
    return u'\n'.join(hstrs), nchanges > 0


def _format_changes(changes):
    '''
    Format the changes dict based on what the data is
    '''
    global __opts__  # pylint: disable=W0601

    if not changes:
        return False, u''

    if not isinstance(changes, dict):
        return True, u'Invalid Changes data: {0}'.format(changes)

    ret = changes.get('ret')
    if ret is not None and changes.get('out') == 'highstate':
        ctext = u''
        changed = False
        for host, hostdata in six.iteritems(ret):
            s, c = _format_host(host, hostdata)
            ctext += u'\n' + u'\n'.join((u' ' * 14 + l) for l in s.splitlines())
            changed = changed or c
    else:
        changed = True
        opts = __opts__.copy()
        # Pass the __opts__ dict. The loader will splat this modules __opts__ dict
        # anyway so have to restore it after the other outputter is done
        if __opts__['color']:
            __opts__['color'] = u'CYAN'
        __opts__['nested_indent'] = 14
        ctext = u'\n'
        ctext += salt.output.out_format(
                changes,
                'nested',
                __opts__)
        __opts__ = opts
    return changed, ctext


def _strip_clean(returns):
    '''
    Check for the state_verbose option and strip out the result=True
    and changes={} members of the state return list.
    '''
    rm_tags = []
    for tag in returns:
        if isinstance(tag, dict):
            continue
        if returns[tag]['result'] and not returns[tag]['changes']:
            rm_tags.append(tag)
    for tag in rm_tags:
        returns.pop(tag)
    return returns


def _format_terse(tcolor, comps, ret, colors, tabular):
    '''
    Terse formatting of a message.
    '''
    result = u'Clean'
    if ret['changes']:
        result = u'Changed'
    if ret['result'] is False:
        result = u'Failed'
    elif ret['result'] is None:
        result = u'Differs'
    if tabular is True:
        fmt_string = u'{0}{2:>10}.{3:<10} {4:7}   Name: {1}{5}'
    elif isinstance(tabular, str):
        fmt_string = tabular
    else:
        fmt_string = u' {0} Name: {1} - Function: {2}.{3} - Result: {4}{5}'
    msg = fmt_string.format(tcolor,
                            comps[2],
                            comps[0],
                            comps[-1],
                            result,
                            colors['ENDC'],
                            ret)
    return msg
