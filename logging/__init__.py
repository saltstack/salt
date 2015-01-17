#

def error(x):
    raise x
import traceback
class L(object):
    def __init__(self):
        pass

    def __init__(self):
        self.handlers=[]

    def setLevel(self, X):
        pass

    def addHandler(self, X):
        pass

    def error(self,x, exc_info=None ):
        raise Exception(x)

    def critical(self,x, exc_info=None ):
        raise Exception(x)

    def exception(self,x ):
        raise Exception(x)

    def debug(self,x ):
        print "DEBUG",x
        #for line in traceback.format_stack():
        #    print line.strip()  

    def warning(self,x , exc_info=None):
        print "WARN",x
        raise Exception(x)
        #for line in traceback.format_stack():
        #    print line.strip()  

    def trace(self,x ):
        print "TRACE",x
        #for line in traceback.format_stack():
        #    print line.strip()  
l = L()

def getLogger(x=None):
    return l

def handlers():
    pass

class Handler (object):
    def __init__(self, level=0):
        pass

class NullHandler (object):
    def __init__(self, level=0):
        pass

from handlers import *

class LC(object):
    pass

def getLoggerClass():
    return LC

class LL(object):
    def __init__(self, l):
        pass
        
NOTSET=1
DEBUG=2
ERROR=3
CRITICAL=4
INFO=5
WARN=WARNING=6
FATAL=7


class LogRecord(object):
    pass


class Formatter(object):
    def __init__(self, x, datefmt):
        pass

def setLoggerClass(x):
    pass

def addLevelName(n, m):
    pass

class Root(L):

    pass

root = Root()

def captureWarnings(x):
    pass
