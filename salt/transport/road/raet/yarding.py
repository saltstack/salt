# -*- coding: utf-8 -*-
'''
yarding.py raet protocol estate classes
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
                  name='',
                  mid=0,
                  ha='',
                  dirpath=None,
                  prefix='lane'):
        '''
        Initialize instance
        '''
        self.stack = stack
        if yid is None:
            yid = Yard.Yid
            Yard.Yid += 1
        elif yid == Yard.Yid:
            Yard.Yid += 1

        if not name and ha:
            name = Yard.nameFromHa(ha)

        self.name = name or "yard{0}".format(yid)
        if " " in self.name:
            emsg = "Invalid Yard name '{0}'".format(self.name)
            raise raeting.YardError(emsg)

        self.mid = mid #current message id

        if dirpath is None:
            dirpath = YARD_UXD_DIR
        self.dirpath = dirpath

        if " " in prefix:
            emsg = "Invalid prefix '{0}'".format(prefix)
            raise raeting.YardError(emsg)
        self.prefix = prefix

        if ha and Yard.nameFromHa(ha) != self.name:
            emsg =  "Incompatible Yard name '{0}' and ha '{1}'".format(self.name, ha)
            raise raeting.YardError(emsg)

        self.ha = ha or os.path.join(dirpath, "{0}.{1}.uxd".format(prefix, self.name))

    @staticmethod
    def nameFromHa(ha):
        '''
        Extract and return the yard name from yard host address ha
        '''
        head, tail = os.path.split(ha)
        if not tail:
            emsg = "Invalid format for ha '{0}'. No file".format(ha)
            raise  raeting.YardError(emsg)

        root, ext = os.path.splitext(tail)

        if ext != ".uxd":
            emsg = "Invalid format for ha '{0}'. Ext not 'uxd'".format(ha)
            raise  raeting.YardError(emsg)

        lane, sep, name = root.rpartition('.')
        if not sep:
            emsg = "Invalid format for ha '{0}'. Not lane.name".format(ha)
            raise  raeting.YardError(emsg)

        return name

    def nextMid(self):
        '''
        Generates next message id number.
        '''
        self.mid += 1
        if self.mid > 0xffffffffL:
            self.mid = 1  # rollover to 1
        return self.mid

    def validMid(self, mid):
        '''
        Compare new mid to old .mid and return True if new is greater than old
        modulo N where N is 2^32 = 0x100000000
        And greater means the difference is less than N/2
        '''
        return (((mid - self.mid) % 0x100000000) < (0x100000000 // 2))

class LocalYard(Yard):
    '''
    RAET UXD Protocol endpoint local Yard
    '''
    def __init__(self, main=False, **kwa):
        '''
        Setup Yard instance
        '''
        super(LocalYard, self).__init__(**kwa)
        self.main = True if main else False # main yard on lane


class RemoteYard(Yard):
    '''
    RAET protocol endpoint remote yard
    '''
    def __init__(self, rmid=0, **kwa):
        '''
        Setup Yard instance
        '''
        super(RemoteYard, self).__init__(**kwa)
        self.rmid = rmid # last mid received from remote

    def validRmid(self, rmid):
        '''
        Compare new rmid to old .rmid and return True if new is greater than old
        modulo N where N is 2^32 = 0x100000000
        And greater means the difference is less than N/2
        '''
        return (((rmid - self.rmid) % 0x100000000) < (0x100000000 // 2))
