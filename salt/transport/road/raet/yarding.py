# -*- coding: utf-8 -*-
'''
devicing.py raet protocol device classes
'''
# pylint: skip-file
# pylint: disable=W0611
# Import python libs
import socket
import os

# Import ioflo libs
from ioflo.base.odicting import odict
from ioflo.base import aiding

from . import raeting
from . import nacling

from ioflo.base.consoling import getConsole
console = getConsole()

YARD_UXD_DIR = os.path.join('/tmp', 'raet')

class Yard(object):
    '''
    RAET protocol Yard
    '''
    Yid = 0 # class attribute

    def  __init__(self,
                  stack=None,
                  yid=None,
                  name="",
                  ha="",
                  dirpath=YARD_UXD_DIR,
                  prefix='yard'):
        '''
        Initialize instance
        '''
        self.stack = stack
        if yid is None:
            yid = Yard.Yid
            Yard.Yid += 1

        self.yid = yid # yard ID
        self.name = name or "{0}{1}".format(prefix, self.yid)
        if " " in self.name:
            emsg = "Invalid Yard name '{0}'".format(self.name)
            raise raeting.YardError(emsg)

        if self.stack:
            stackname = self.stack.name
        else:
            stackname = stack

        self.ha = ha or os.path.join(dirpath, "{0}.uxd.{1}".format(
                stackname, self.name))


