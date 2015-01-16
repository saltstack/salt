import sys
import os
import re

sed = {}
def check(fn):
    #print("Consider {0}".format(fn))
    f=open(fn)
    for l in f.readlines():
        l = l.rstrip()
        m = re.match(r'(\s+)except\s+([\\,\s\w(\)]+):', l)
        if m :
            (s,e)=m.groups()
            if 'as' not in e:
                #print "Found:",e
                r =  s + "except "+ e + ' as exp:\\n' + "{0}    log.error('{1}'.format(exp))".format(s ,e + " {0}")

                if l not in sed:
                    sed[l]={
                        'r':r,
                        'files' : [ ]
                    }
                sed[l]['files'].append(fn)


    f.close()
for root, dirs, files in os.walk("./"):
    for filen in files:
        if filen.endswith(".py"):
            check(root + "/" +filen )
    

for x in sed:
    r = sed[x]['r']
    r = r.replace("'","\'")
    r = r.replace(" "," ")
    f = " " .join(sed[x]['files'])
    x = x.replace(" ","\s")
    print "sed -i.bak -e\"s;{0};{1};\" {2}".format(x,r, f)
