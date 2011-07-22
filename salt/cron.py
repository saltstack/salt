#!/usr/bin/env python

'''
Parse time and cron related structures.
This module is used by salt.monitor to schedule command execution.
'''

import locale
import re
import sys

def parse_interval(interval_dict):
    '''Translate a time interval dict into a number of seconds.
       The interval_dict is expected to have one or more of the
       following keys which map to numeric (integer or float)
       values: day, hour, minute, second.  Missing keys default
       to zero.  All other dict entries are ignored.

       >>> parse_interval({'day':1, 'hour':2, 'minute':3, 'second':4.5})
       93784.5
       >>> parse_interval({'second':10})
       10
    '''
    return (((interval_dict.get('day', 0) * 24 +
              interval_dict.get('hour', 0)) * 60 +
              interval_dict.get('minute', 0)) * 60 +
              interval_dict.get('second', 0))

class CronParser(object):
    '''Translate 'cron' dictionaries into timeout generators.
       A cron dict may contain 'month', 'day', 'weekday', 'hour',
       'minute', and 'second' entries were each value is a UNIX
       crontab field.  For example, {'hour': '0, 1-3, 18-23/2'}
       will generate the number of seconds to sleep until the hour
       is 0 (midnight), 1, 2, 3, 18, 20, or 22.

       The crontab format is:
            * [ / incr ]
            start [ - end [ / incr ] ]
        where
            start = an integer (e.g. 1 or 2) or a name (e.g. jan or tuesday)
            end   = an integer (e.g. 3 or 4) or a name (e.g. may or friday)
            incr  = an integer indicating the step from start to end,
                    e.g. start=1, end=5, and incr=2 produces [1,3,5]

        A name can be specified for the month and weekday entries.
        Legal values include the full and abbreviated names in your
        locale.  For example, in the 'C' locale, valid weekday names
        include 'Monday', 'mon', 'Tuesday', 'tue', etc.  The names
        are case-insensitive.

        See also: cron(5), locale(1)

        >>> p = CronParser()
        >>> actual = p.parse({'hour': '1,2-3,18-23/2', 'weekday': 'mon-Friday/2,sunday'})
        >>> expected = {'hour': [1, 2, 3, 18, 20, 22], 'weekday': [1, 2, 4, 6] }
        >>> actual == expected
        True
    '''
    def __init__(self):
        # load the locale's month names and abbreviations
        self.months = {}
        for i in range(1, 13):
            for basename in ['MON_{}', 'ABMON_{}']:
                index = locale.__dict__[basename.format(i)]
                name = locale.nl_langinfo(index).lower()
                self.months[name] = i

        # load the locale's weekday names and abbreviations
        self.weekdays = {}
        for i in range(1, 8):
            for basename in ['DAY_{}', 'ABDAY_{}']:
                index = locale.__dict__[basename.format(i)]
                name = locale.nl_langinfo(index).lower()
                self.weekdays[name] = i

        # compile the cron entry pattern
        self.cron_pattern = re.compile(r'''
            (?: (?P<all> \*)
                (?: \s* / \s* (?P<allincr> \d+ ) )? [, \t]* ) |
            (?: (?P<start> \w+)
                (?: \s* - \s*
              (?P<end> \w+ )
                (?: \s* / \s* (?P<incr> \d+ ) )? )? [, \t]* ) |
            (?P<comma>,)|
            (?P<cruft>\S+?)
            ''',
            re.VERBOSE)

    def parse(self, cron_dict):
        '''Parse a cron dict into a structure usable for the cron timer.
        '''
        result = {}
        for key, enums, minval, maxval in [
                ('month',   self.months,   1, 12),
                ('day',     None,          1, 31),
                ('weekday', self.weekdays, 1, 7),
                ('hour',    None,          0, 23),
                ('minute',  None,          0, 59),
                ('second',  None,          0, 61)]:
            field = cron_dict.get(key)
            if field:
                value = self._parse_cron_field(field, enums, minval, maxval)
                result[key] = value
        return result

    def _parse_cron_field(self, field, enums, minval, maxval):
        '''Parse one cron field into a list of numbers.
        '''
        result = set()
        for match in self.cron_pattern.finditer(field):
            start_str, end_str, incr_str = self._extract_cron_groups(match)
            comma = match.group('comma')
            if not (start_str or end_str or incr_str) and comma:
                continue
            try:
                if start_str == '*':
                    start = 1
                    end = maxval
                else:
                    start = self._to_number(start_str, enums, minval, maxval)
                    end = self._to_number(end_str, enums, minval, maxval, start)
                incr = self._to_number(incr_str, enums, minval, maxval, 1)
            except ValueError, ex:
                ex2 = ValueError('{} in \'{}\''.format(ex, field))
                raise ex2, None, sys.exc_info()[2]
            if start > end:
                raise ValueError('invalid cron range \'{}-{}\' in \'{}\''
                                    .format(start_str, end_str, field))
            cruft = match.group('cruft')
            if cruft:
                canonical = self._tuples_to_string(result)
                raise ValueError('cron syntax error: {} >>> {} <<<'
                                    .format(canonical, cruft))
            result.update(range(start, end+1, incr))
        return sorted(result)

    def _extract_cron_groups(self, match):
        '''Extract a (start, end, incr) tuple from a regex match.
        '''
        if match.group('all') == '*':
            start = '*'
            end = '*'
            incr = match.group('allincr')
        else:
            start = match.group('start')
            end = match.group('end')
            incr = match.group('incr')
        return (start, end, incr)

    def _to_number(self, num_str, enums, minval, maxval, defval=None):
        '''Convert a parsed word into an integer.
           num_str  = the string to be converted or None
           enums    = a word-to-integer mapping used to convert words
                     like 'February' and 'feb' to a number like 2.
                     The keys must be lowercased.
           minval  = the minimum legal value
           maxval  = the maximum legal value
           defval  = the default value if num_str is None or blank.
                     This value can be anything, not just an integer.
           Returns an integer or defval

           >>> p = CronParser()
           >>> p._to_number('1', p.months, 1, 12)
           1
           >>> p._to_number('FEBRUARY', p.months, 1, 12)
           2
           >>> p._to_number(' AuG ', p.months, 1, 12)
           8
           >>> p._to_number('', p.months, 1, 12,'foo')
           'foo'
        '''
        if num_str is None:
            result = defval
        else:
            cleaned = num_str.strip().lower()
            if len(cleaned) == 0:
                result = defval
            elif cleaned.isdigit():
                result = int(cleaned)
                if not minval <= result <= maxval:
                    raise ValueError('cron value out of bounds [{},{}]: {}'
                                        .format(minval, maxval, num_str))
            else:
                result = enums.get(cleaned)
                if result is None:
                    raise ValueError('invalid cron value: \'{}\''
                                        .format(num_str))
        return result

    def _tuples_to_string(self, entries):
        '''Convert a list of (start,end,incr) tuples into a printable string.

           >>> p = CronParser()
           >>> p._tuples_to_string([ (9, None, None), (1,3,None), ('*','*',2) ])
           '9, 1-3, */2'
        '''
        result = ''
        for start, end, incr in entries:
            if len(result) > 0:
                result += ', '
            if start == '*':
                result += '*'
            else:
                if start is not None:
                    result += str(start)
                    if end is not None:
                        result += '-' + str(end)
            if incr is not None:
                result += '/' + str(incr)
        return result
