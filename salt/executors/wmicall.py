# -*- coding: utf-8 -*-
'''
Windows WMI call module

@author: Erin Scanlon <escanlon@singlehop.com>
'''
from __future__ import absolute_import
import os
import logging
from salt.executors import ModuleExecutorBase

def get(cmd):
    return WMICall(cmd)

class WMICall(ModuleExecutorBase):
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
        self.log.trace("potato initialization")
        self.log.trace(self.wmitarget)

    def execute(self):
        '''
        Call a windows function and return the results
        Assumes the wmiinput in the constructor is a WMI object
        Chainable
        '''
        self.log.trace("wmi execute is running")
        self.wmiresult = os.popen('wmic path %s %s' % (self.wmitarget ,' 2>&1'),'r').read().strip()
        self.log.trace(self.wmiresult)
        return self

    def executepure(self):
        '''
        Call a windows function and return the results
        Assumes the wmiinput in the constructor is a full command
        Chainable
        '''
        self.log.trace("wmi executepure is running")
        self.wmiresult = os.popen('%s %s' % (self.wmitarget ,' 2>&1'),'r').read().strip()
        self.log.trace(self.wmiresult)
        return self

    def formatresponse(self):
        '''
        Parse and format the response from a windows command line WMI request
        Used when the command line request returns a stringified 'table' of results
        '''
        self.log.trace('formatting windows wmi call response')
        arr = self.wmiresult.split()
        intlist = [x for x in arr if x.isdigit()]
        self.log.trace(intlist)
        strlist = [x for x in arr if not x.isdigit()]
        self.log.trace(strlist)
        return dict(zip(strlist, intlist))
