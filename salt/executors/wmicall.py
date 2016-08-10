# -*- coding: utf-8 -*-
'''
Windows WMI call module

@author: Erin Scanlon <escanlon@singlehop.com>
'''

import os
import logging

__virtualname__ = 'WMICall'

def __virtual__():
    return __virtualname__

class WMICall:
    '''
    Call with a WMI target to get. Obtains and formats.

    Example:
        foo = new WindowsCall('Win32_PerfFormattedData_PerfOS_Memory')
        resultdict = foo.formatresponse(foo.execute)

    '''

    def __init__(self, wmiinput):
        '''
        Constructor
        '''
        self.wmitarget = wmiinput
        self.wmiresult = ''
        self.log = logging.getLogger(__name__)

    def execute(self):
        '''
        Call a windows function and return the results
        Chainable
        '''
        self.log.trace("wmi execute is running")
        self.wmiresult = os.popen('wmic path %s %s' % (self.wmitarget ,' 2>&1'),'r').read().strip()
        self.log.trace(self.wmiresult)
        return self

    def formatresponse():
        '''
        Parse and format the response from a windows command line WMI request
        Used when the command line request returns a stringified 'table' of results
        '''
        self.log.trace('formatting windows wmi call response')
        arr = self.wmiresult.split()
        intlist = [x for x in arr if x.isdigit()]
        strlist = [x for x in arr if not x.isdigit()]
        return dict(zip(strlist, intlist))
