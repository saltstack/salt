"""
    :codeauthor: Romeo Solano <rsolano@systemsbiology.org>
"""
import pytest
import salt.states.zabbix_host as zabbix_host
from tests.support.mock import MagicMock, patch
from collections import OrderedDict

DEFINED_SNMP3_HOST_PARAMS = {
    "name": "hostname",
    "groups": [
        '19',
        '20'
    ],
    # I am not a python developer. This looks weird to me
    "interfaces": [
        OrderedDict([('snmp_interface', 
            [OrderedDict([('type', 'snmp')]), 
	            OrderedDict([('dns', 'hostname')]),
	            OrderedDict([('ip', '10.10.10.10')]),
	            OrderedDict([('port', '161')]), 
	            OrderedDict([('useip', True)]),
	            OrderedDict([('main', True)]),
	            OrderedDict([('details', [
	                OrderedDict([('version', '3')]), 
	                OrderedDict([('bulk', '1')]), 
	                OrderedDict([('securityname', 'securityname')]), 
	                OrderedDict([('securitylevel', '2')]), 
	                OrderedDict([('authpassphrase', 'authpassphrase')]), 
	                OrderedDict([('authprotocol', '0')]), 
	                OrderedDict([('privpassphrase', 'authpassphrase')]), 
	                OrderedDict([('privprotocol', '1')])
	            ])])
            ])]
        )
    ]
}

DEFINED_SNMP2_HOST_PARAMS = {
    "name": "hostname",
    "groups": [
        '19',
        '20'
    ],
    "interfaces": [
        OrderedDict([('snmp_interface', 
            [OrderedDict([('type', 'snmp')]), 
	            OrderedDict([('dns', 'hostname')]),
	            OrderedDict([('ip', '10.10.10.10')]),
	            OrderedDict([('port', '161')]), 
	            OrderedDict([('useip', True)]),
	            OrderedDict([('main', True)]),
	            OrderedDict([('details', [
	                OrderedDict([('version', '2')]), 
	                OrderedDict([('bulk', '1')]), 
	            ])])
            ])]
        )
    ]
}

@pytest.fixture
def setup_loader_modules():
    return {zabbix_host: {}}

def test__interface_format_no_community_in_snmp3():
    """
    Test if the "community" string gets added to SNMPv3 interfaces (basically)
    """
    assert 'community' not in zabbix_host._interface_format(DEFINED_SNMP3_HOST_PARAMS['interfaces'])[0]['details']

def test__interface_format_yes_community_in_snmp2():
    """
    Test that the "community" string gets added to SNMPv2 interfaces
    """
    assert 'community' in zabbix_host._interface_format(DEFINED_SNMP2_HOST_PARAMS['interfaces'])[0]['details']
