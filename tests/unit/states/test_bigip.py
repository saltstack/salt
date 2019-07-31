# -*- coding: utf-8 -*-
'''
    :codeauthor: Jérôme O'Keeffe
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    patch,
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt LibsAh    
import salt.modules.bigip as bigip


class MockBigipModule(object):
    def __init__(self):
        pass

    def list_irule(hostname, username, password, name=None, partition=None):
        partition = partition if partition else 'Common'
        link_prefix = 'https://{hostname}/mgmt/tm/ltm/rule/'.format(hostname=hostname)
        res = {}
        res['code'] = 200
        if name:
            res['content'] = {
                'kind': 'tm:ltm:rule:rulestate',
                'name': name,
                'parition': partition,
                'fullPath': '/{partition}/{name}'.format(
                    partition=partition,
                    name=name),
                'generation': 1,
                'selfLink': '{link_prefix}/~{partition}~{name}'.format(
                    link_prefix=link_prefix,
                    partion=partition,
                    name=name),
                'api_anonymous': 'TCL code'
            }
        else:
            res['content'] = [{
                'kind': 'tm:ltm:rule:rulestate',
                'name': 'name1',
                'parition': partition,
                'fullPath': '/{partition}/name1'.format(partion=partition),
                'generation': 1,
                'selfLink': '{link_prefix}/~{partition}~name1'.format(
                    link_prefix=link_prefix,
                    partition=partition
                ),
                'api_anonymous': 'TCL code'
            }, {
                'kind': 'tm:ltm:rule:rulestate',
                'name': 'name2',
                'parition': partition,
                'fullPath': '/{partition}/name2'.format(partion=partition),
                'generation': 1,
                'selfLink': '{link_prefix}/~{partition}~name2'.format(
                    link_prefix=link_prefix,
                    partition=partition
                ),
                'api_anonymous': 'TCL code'
            }]
        # raise Exception('ldld')
        return res

    def create_irule():
        pass

    def modify_irule():
        pass

    def delete_irule():
        pass


@patch('salt.modules.bigip.list_irule', MockBigipModule.list_irule
@patch('salt.modules.bigip.create_irule', MockBigipModule.list_irule)
# @patch('salt.modules.bigip.create_irule', MagicMock())
class BigipTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {bigip: {}}

    def test_create_irule_that_already_exist(self):
        assert_res = {
            'result': True,
            'comment': 'An iRule by this name currently exists. No change made.'
        }

        res = bigip.create_irule('', '', '', 'name', '', partition='singlebuild')
        try:        
            assert res == assert_res
        except AssertionError as e:
            # type(res), res, dir(res),
            e.args += (dir(res), 'hellp')
            raise
