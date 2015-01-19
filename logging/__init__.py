#

def error(x):
    raise x
import traceback
class L(object):
    def __init__(self):
        self.handlers=[]

    def setLevel(self, X):
        pass

    def addHandler(self, X):
        pass
    def isEnabledFor(self,x):
        return True
    def error(self,x, exc_info=None , exc_info_on_loglevel=None):
        raise Exception(x)

    def log(self,x, exc_info=None , exc_info_on_loglevel=None):
        print "LOG",x        

    def critical(self,x , exc_info=None , exc_info_on_loglevel=None  ):
        raise Exception(x)

    def exception(self,x , exc_info=None , exc_info_on_loglevel=None  ):
        raise Exception(x)

    def debug(self,x, exc_info=None , exc_info_on_loglevel=None  ):
        #print "DEBUG",x
        #for line in traceback.format_stack():
        #    print line.strip()  
        pass

    def warning(self,x , exc_info=None , exc_info_on_loglevel=None ):
        #print "WARN",x
        #raise Exception(x)
        #for line in traceback.format_stack():
        #    print line.strip()  
        pass

    def info(self,x , exc_info=None , exc_info_on_loglevel=None ):
        #print "INFO",x
        #raise Exception(x)
        pass

    def trace(self,x , exc_info=None , exc_info_on_loglevel=None  ):
        #print "TRACE",x
        #for line in traceback.format_stack():
        #    print line.strip()  
        pass
l = L()

class G:
    def __init__(self):
        self.emittedNoHandlerWarning= 0
    
class F:
    def __init__(self):
        self.manager = G()
        self.loggerDict={}

Logger = F()

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
    def _log(self, level=None, msg=None, args=None, exc_info=None, extra=None):
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
    def __init__(self, x, datefmt=None):
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

def getLevelName(x):
    return "DEBUG"

def basicConfig(
        filename,
        format,
        datefmt,
        level):
    pass
