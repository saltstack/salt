#!pydsl|stateconf -ps
include('pydsl.xxx')
__pydsl__.set(ordered=True)
state('.Y1').cmd.run('echo Y1 >> {0}'.format('/tmp/output'), cwd='/')
state('.Y2').cmd.run('echo Y2 >> {0}'.format('/tmp/output'), cwd='/')
state('.Y3').cmd.run('echo Y3 >> {0}'.format('/tmp/output'), cwd='/')
def hello(color, number):
    state(color).cmd.run('echo hello '+color+' '+str(number)+' >> {0}'.format('/tmp/output'), cwd='/')
