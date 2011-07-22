#!/usr/bin/env python

import doctest
import locale
import unittest

import salt.cron

class TestTime(unittest.TestCase):

    def setUp(self):
        self.cron = salt.cron.CronParser()

    def _test_interval(self, intime, expected):
        actual = salt.cron.parse_interval(intime)
        self.assertEqual(actual, expected)

    def _test_parse_cron(self, intime, expected):
        actual = self.cron.parse(intime)
        self.assertEqual(actual, expected)

    def _test_parse_group(self, unit, values, expected):
        for value in values:
            self._test_parse_cron({unit : value}, {unit : [expected]})

    def test_doc(self):
        doctest.testmod(salt.cron)

    def test_interval(self):
        self._test_interval({'second'  : 1}, 1)
        self._test_interval({'seconds' : 1}, 1)
        self._test_interval({'minute'  : 1}, 60)
        self._test_interval({'minutes' : 1}, 60)
        self._test_interval({'hour'    : 1}, 60 * 60)
        self._test_interval({'hours'   : 1}, 60 * 60)
        self._test_interval({'day'     : 1}, 24 * 60 * 60)
        self._test_interval({'days'    : 1}, 24 * 60 * 60)

        self._test_interval({'second' : 10},    10)        # 10 seconds
        self._test_interval({'second' : 0.123}, 0.123)
        self._test_interval({'minute' : 0.5},   30)        # 30 seconds
        self._test_interval({'minute' : 5},     300)       # 5 minutes
        self._test_interval({'hour'   : 0.25},  15 * 60)   # 15 minutes
        self._test_interval({'day'    : 2,
                             'hour'   : 3,
                             'minute' : 4,
                             'second' : 5},     2 * 24 * 60 * 60 +
                                                3 * 60 * 60 +
                                                4 * 60 +
                                                5)

    def test_cron_parse_month(self):
        self._test_parse_group('month', ('January',   'jan', '1'), 1)
        self._test_parse_group('month', ('February',  'feb', '2'), 2)
        self._test_parse_group('month', ('March',     'mar', '3'), 3)
        self._test_parse_group('month', ('April',     'apr', '4'), 4)
        self._test_parse_group('month', ('May',       'may', '5'), 5)
        self._test_parse_group('month', ('June',      'jun', '6'), 6)
        self._test_parse_group('month', ('July',      'jul', '7'), 7)
        self._test_parse_group('month', ('August',    'aug', '8'), 8)
        self._test_parse_group('month', ('September', 'sep', '9'), 9)
        self._test_parse_group('month', ('October',   'oct', '10'), 10)
        self._test_parse_group('month', ('November',  'nov', '11'), 11)
        self._test_parse_group('month', ('December',  'dec', '12'), 12)

        self._test_parse_cron({'month' : '*'},
                              {'month' : [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]})
        self._test_parse_cron({'month' : '3-6,11-12'},
                              {'month' : [3, 4, 5, 6, 11, 12]})
        self._test_parse_cron({'month' : 'mar - june, nov-DeceMbEr'},
                              {'month' : [3, 4, 5, 6, 11, 12]})
        self._test_parse_cron({'month' : ', ,mar- june /2  nov -DeceMbEr/1,,, '},
                              {'month' : [3, 5, 11, 12]})

    def test_cron_parse_weekday(self):
        self._test_parse_group('weekday', ('Sunday',    'sun', '1'), 1)
        self._test_parse_group('weekday', ('Monday',    'mon', '2'), 2)
        self._test_parse_group('weekday', ('Tuesday',   'tue', '3'), 3)
        self._test_parse_group('weekday', ('Wednesday', 'wed', '4'), 4)
        self._test_parse_group('weekday', ('Thursday',  'thu', '5'), 5)
        self._test_parse_group('weekday', ('Friday',    'fri', '6'), 6)
        self._test_parse_group('weekday', ('Saturday',  'sat', '7'), 7)

        self._test_parse_cron({'weekday' : '*'}, {'weekday' : [1, 2, 3, 4, 5, 6, 7]})
        self._test_parse_cron({"weekday" : "monday-friday"}, {"weekday" : [2, 3, 4, 5, 6]})
        self._test_parse_cron({"weekday" : "wed-sat"},       {"weekday" : [4, 5, 6, 7]})
        self._test_parse_cron({"weekday" : "wed-sat/2"},     {"weekday" : [4, 6]})

def test_suite():
    locale.setlocale(locale.LC_ALL, 'C')
    return unittest.TestLoader().loadTestsFromName(__name__)
