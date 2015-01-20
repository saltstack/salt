import traceback
import sys
#def myexceptions(type, value, tb, pylibdir=None, nlev=None):
#    traceback.print_exception(type, value, tb, nlev)
import inspect

#sys.excepthook=myexceptions
import sys
import traceback


def error(x):
    raise x

class L(object):
    def __init__(self):
        self.handlers=[]

    def setLevel(self, X):
        pass

    def addHandler(self, X):
        pass
    def isEnabledFor(self,x):
        return True


    def critical(self,x , exc_info=None , exc_info_on_loglevel=None ,*args,**kwargs ):
        print(traceback.format_exc())
        raise Exception(x)

    def exception(self,x , exc_info=None , exc_info_on_loglevel=None ,*args,**kwargs ):
        print(traceback.format_exc())
        raise Exception(x)

    def error(self,x, exc_info=None , exc_info_on_loglevel=None,*args,**kwargs):
        print(traceback.format_exc())
        raise Exception(x)

    def setup_extended_logging(self,*args,**kwargs):
        pass

    def setup_console_logger(self,*args,**kwargs):
        pass

    def setup_logfile_logger(self,*args,**kwargs):
        pass

    def setup_temp_logger(
            level=None,
            *args,
            **kwargs
        ):
        pass

    def log(self,msg=None, level=None, exc_info=None , exc_info_on_loglevel=None ,*args,**kwargs):
        print "LOG",msg        

    def debug(self,*args,**kwargs ):
        #print "DEBUG",x
        #for line in traceback.format_stack():
        #    print line.strip()  
        pass
    LOG_LEVELS = ("DEBUG","WARN","quiet",'error')
    SORTED_LEVEL_NAMES = ("DEBUG","WARN")
    def warning(self,x , exc_info=None , exc_info_on_loglevel=None,*args,**kwargs ):
        #print "WARN",x
        #raise Exception(x)
        #for line in traceback.format_stack():
        #    print line.strip()  
        pass

    def info(self,x , exc_info=None , exc_info_on_loglevel=None ,*args,**kwargs):
        #print "INFO",x
        #raise Exception(x)
        pass

    def trace(self,x , exc_info=None , exc_info_on_loglevel=None ,*args,**kwargs ):
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

    def setFormatter(self,x):
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
        filename=None,
        format=None,
        datefmt=None,
        level=None):
    pass
