import yaml
import sys
from jinja2 import Environment, PackageLoader, Template
import os

# shebangs
#!yaml_jinja
#!yaml_mako
#!mako|yaml
#!jinja|yaml
#!jinja|mako|yaml
#!mako|yaml|stateconf
#!jinja|yaml|stateconf
#!mako|yaml_odict
#!mako|yaml_odict|stateconf

def check(fn):
    #print fn
    print("Consider {0}".format(fn))
    r = os.system("~/.local/bin/pylint -E --rcfile=pylint.rc %s" % fn)
    if r not in (0, 512) : # 512= check failed
        raise Exception('fail %s'  % r)
    # f = open (fn)
    # data = ""
    # c = 0
    # firstline = ""
    # for x in f.readlines():
    #     if c == 0 :
    #         #print x
    #         firstline = x
    #     c = c + 1
    #     data = data + x
    # try :
    #     eval(data)
    #     print 'PYOK', fn
    # except Exception as e2 :
    #     print "Python failed:",e2
    #     #print data
        


for root, dirs, files in os.walk("./"):
    for filen in files:
        if filen.endswith(".py"):
            check(root + "/" +filen )
    

