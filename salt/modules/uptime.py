'''
    Get various uptime statistics for machine
    Provides
        uptime days
        uptime hours
        uptime minutes
        uptime seconds
'''
raw = __salt__['cmd.run']('uptime').replace(',','')
array = raw.split()
if len(array) < 11:
    totaldays = 0
    numberforsplit = 2
else:
    totaldays = int(raw.split()[2])
    numberforsplit = 4
if 'min' in raw:
    totalhours = 0
    totalminutes = int(raw[2])
else:
    totalhours, totalminutes = map(int,raw.split()[numberforsplit].split(':'))

def full():
    return __salt__['cmd.run']('uptime')

def days():
    return totaldays

def hours():
    return totalhours

def minutes():
    minutes = totaldays*1440 + totalhours*60 + totalminutes
    return minutes

def seconds():
    totalsecs = totaldays*24*60*60 + totalhours*60*60 + totalminutes*60
    return totalsecs
