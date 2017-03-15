# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf

# Import Salt Libs
import salt.utils.http
from salt.modules import random_org

random_org.__opts__ = {}


def check_status():
    '''
    Check the status of random.org
    '''
    try:
        ret = salt.utils.http.query('https://api.random.org/', status=True)
        return ret['status'] == 200
    except:  # pylint: disable=W0702
        return False


@skipIf(not check_status(), 'random.org is not available')
class RandomOrgTestCase(TestCase):
    '''
    Test cases for salt.modules.random_org
    '''
    # 'getUsage' function tests: 1

    def test_getusage(self):
        '''
        Test if it show current usages statistics.
        '''
        ret = {'message': 'No Random.org api key or api version found.',
               'res': False}
        self.assertDictEqual(random_org.getUsage(), ret)

        self.assertDictEqual(random_org.getUsage(api_key='peW',
                                                 api_version='1'),
                             {'bitsLeft': None, 'requestsLeft': None,
                              'res': True, 'totalBits': None,
                              'totalRequests': None})

    # 'generateIntegers' function tests: 1

    def test_generateintegers(self):
        '''
        Test if it generate random integers.
        '''
        ret1 = {'message': 'No Random.org api key or api version found.',
                'res': False}
        self.assertDictEqual(random_org.generateIntegers(), ret1)

        ret2 = {'message': 'Rquired argument, number is missing.', 'res': False}
        self.assertDictEqual(random_org.generateIntegers(api_key='peW',
                                                         api_version='1'), ret2)

        ret3 = {'message': 'Number of integers must be between 1 and 10000',
                'res': False}
        self.assertDictEqual(random_org.generateIntegers(api_key='peW',
                                                         api_version='1',
                                                         number='5',
                                                         minimum='1',
                                                         maximum='6'), ret3)

        ret4 = {'message': ('Minimum argument must be between -1,000,000,000'
                            ' and 1,000,000,000'), 'res': False}
        self.assertDictEqual(random_org.generateIntegers(api_key='peW',
                                                         api_version='1',
                                                         number=5, minimum='1',
                                                         maximum='6'), ret4)

        ret5 = {'message': ('Maximum argument must be between -1,000,000,000'
                            ' and 1,000,000,000'), 'res': False}
        self.assertDictEqual(random_org.generateIntegers(api_key='peW',
                                                         api_version='1',
                                                         number=5, minimum=1,
                                                         maximum='6'), ret5)

        ret6 = {'message': 'Base must be either 2, 8, 10 or 16.', 'res': False}
        self.assertDictEqual(random_org.generateIntegers(api_key='peW',
                                                         api_version='1',
                                                         number=5, minimum=1,
                                                         maximum=6, base='2'),
                             ret6)

        ret7 = {'message': u"Parameter 'apiKey' is malformed", 'res': False}
        self.assertDictEqual(random_org.generateIntegers(api_key='peW',
                                                         api_version='1',
                                                         number=5, minimum=1,
                                                         maximum=6, base=2),
                             ret7)

    # 'generateStrings' function tests: 1

    def test_generatestrings(self):
        '''
        Test if it generate random strings.
        '''
        ret1 = {'message': 'No Random.org api key or api version found.',
                'res': False}
        self.assertDictEqual(random_org.generateStrings(), ret1)

        ret2 = {'message': 'Required argument, number is missing.',
                'res': False}
        self.assertDictEqual(random_org.generateStrings(api_key='peW',
                                                        api_version='1'), ret2)

        ret3 = {'message': 'Number of strings must be between 1 and 10000',
                'res': False}
        char = 'abcdefghijklmnopqrstuvwxyz'
        self.assertDictEqual(random_org.generateStrings(api_key='peW',
                                                        api_version='1',
                                                        number='5',
                                                        length='8',
                                                        characters=char), ret3)

        ret3 = {'message': 'Length of strings must be between 1 and 20',
                'res': False}
        self.assertDictEqual(random_org.generateStrings(api_key='peW',
                                                        api_version='1',
                                                        number=5,
                                                        length='8',
                                                        characters=char), ret3)

        ret3 = {'message': 'Length of characters must be less than 80.',
                'res': False}
        self.assertDictEqual(random_org.generateStrings(api_key='peW',
                                                        api_version='1',
                                                        number=5,
                                                        length=8,
                                                        characters=char*4),
                             ret3)

        ret3 = {'message': u"Parameter 'apiKey' is malformed",
                'res': False}
        self.assertDictEqual(random_org.generateStrings(api_key='peW',
                                                        api_version='1',
                                                        number=5,
                                                        length=8,
                                                        characters=char), ret3)

    # 'generateUUIDs' function tests: 1

    def test_generateuuids(self):
        '''
        Test if it generate a list of random UUIDs.
        '''
        ret1 = {'message': 'No Random.org api key or api version found.',
                'res': False}
        self.assertDictEqual(random_org.generateUUIDs(), ret1)

        ret2 = {'message': 'Required argument, number is missing.',
                'res': False}
        self.assertDictEqual(random_org.generateUUIDs(api_key='peW',
                                                      api_version='1'), ret2)

        ret3 = {'message': 'Number of UUIDs must be between 1 and 1000',
                'res': False}
        self.assertDictEqual(random_org.generateUUIDs(api_key='peW',
                                                      api_version='1',
                                                      number='5'), ret3)

        ret3 = {'message': u"Parameter 'apiKey' is malformed",
                'res': False}
        self.assertDictEqual(random_org.generateUUIDs(api_key='peW',
                                                      api_version='1',
                                                      number=5), ret3)

    # 'generateDecimalFractions' function tests: 1

    def test_generatedecimalfractions(self):
        '''
        Test if it generates true random decimal fractions.
        '''
        ret1 = {'message': 'No Random.org api key or api version found.',
                'res': False}
        self.assertDictEqual(random_org.generateDecimalFractions(), ret1)

        ret2 = {'message': 'Required argument, number is missing.',
                'res': False}
        self.assertDictEqual(random_org.generateDecimalFractions
                             (api_key='peW', api_version='1'), ret2)

        ret3 = {'message': ('Number of decimal fractions must be'
                            ' between 1 and 10000'), 'res': False}
        self.assertDictEqual(random_org.generateDecimalFractions
                             (api_key='peW', api_version='1', number='5',
                              decimalPlaces='4', replacement=True), ret3)

        ret4 = {'message': 'Number of decimal places must be between 1 and 20',
                'res': False}
        self.assertDictEqual(random_org.generateDecimalFractions
                             (api_key='peW', api_version='1', number=5,
                              decimalPlaces='4', replacement=True), ret4)

        ret5 = {'message': u"Parameter 'apiKey' is malformed", 'res': False}
        self.assertDictEqual(random_org.generateDecimalFractions
                             (api_key='peW', api_version='1', number=5,
                              decimalPlaces=4, replacement=True), ret5)

    # 'generateGaussians' function tests: 1

    def test_generategaussians(self):
        '''
        Test if it generates true random numbers from a
        Gaussian distribution (also known as a normal distribution).
        '''
        ret1 = {'message': 'No Random.org api key or api version found.',
                'res': False}
        self.assertDictEqual(random_org.generateGaussians(), ret1)

        ret2 = {'message': 'Required argument, number is missing.',
                'res': False}
        self.assertDictEqual(random_org.generateGaussians(api_key='peW',
                                                          api_version='1'),
                             ret2)

        ret3 = {'message': ('Number of decimal fractions must be'
                            ' between 1 and 10000'), 'res': False}
        self.assertDictEqual(random_org.generateGaussians
                             (api_key='peW', api_version='1',
                              number='5', mean='0.0', standardDeviation='1.0',
                              significantDigits='8'), ret3)

        ret4 = {'message': ("The distribution's mean must be between"
                            " -1000000 and 1000000"), 'res': False}
        self.assertDictEqual(random_org.generateGaussians
                             (api_key='peW', api_version='1', number=5,
                              mean='0.0', standardDeviation='1.0',
                              significantDigits='8'), ret4)

        ret5 = {'message': ("The distribution's standard deviation must be"
                " between -1000000 and 1000000"), 'res': False}
        self.assertDictEqual(random_org.generateGaussians
                             (api_key='peW', api_version='1', number=5,
                              mean=0.0, standardDeviation='1.0',
                              significantDigits='8'), ret5)

        ret6 = {'message': ('The number of significant digits must be'
                ' between 2 and 20'), 'res': False}
        self.assertDictEqual(random_org.generateGaussians
                             (api_key='peW', api_version='1', number=5,
                              mean=0.0, standardDeviation=1.0,
                              significantDigits='8'), ret6)

        ret7 = {'message': u"Parameter 'apiKey' is malformed", 'res': False}
        self.assertDictEqual(random_org.generateGaussians(api_key='peW',
                                                          api_version='1',
                                                          number=5, mean=0.0,
                                                          standardDeviation=1.0,
                                                          significantDigits=8),
                             ret7)

    # 'generateBlobs' function tests: 1

    def test_generateblobs(self):
        '''
        Test if it list all Slack users.
        '''
        ret1 = {'message': 'No Random.org api key or api version found.',
                'res': False}
        self.assertDictEqual(random_org.generateBlobs(), ret1)

        ret2 = {'message': 'Required argument, number is missing.',
                'res': False}
        self.assertDictEqual(random_org.generateBlobs(api_key='peW',
                                                      api_version='1'), ret2)

        ret3 = {'message': ('Number of blobs must be between 1 and 100'),
                'res': False}
        self.assertDictEqual(random_org.generateBlobs(api_key='peW',
                                                      api_version='1',
                                                      number='5', size='1'),
                             ret3)

        ret4 = {'message': 'Number of blobs must be between 1 and 100',
                'res': False}
        self.assertDictEqual(random_org.generateBlobs(api_key='peW',
                                                      api_version='1', number=5,
                                                      size=1), ret4)

        ret5 = {'message': 'Format must be either base64 or hex.', 'res': False}
        self.assertDictEqual(random_org.generateBlobs(api_key='peW',
                                                      api_version='1', number=5,
                                                      size=8, format='oct'),
                             ret5)

        ret6 = {'message': u"Parameter 'apiKey' is malformed", 'res': False}
        self.assertDictEqual(random_org.generateBlobs(api_key='peW',
                                                      api_version='1',
                                                      number=5, size=8,
                                                      format='hex'), ret6)
