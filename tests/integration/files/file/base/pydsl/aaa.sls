#!pydsl|stateconf -ps
include('pydsl.xxx')
yyy = include('pydsl.yyy')
# ensure states in xxx are run first, then those in yyy and then those in aaa last.
extend(state('pydsl.yyy::start').stateconf.require(stateconf='pydsl.xxx::goal'))
extend(state('.start').stateconf.require(stateconf='pydsl.yyy::goal'))
extend(state('pydsl.yyy::Y2').cmd.run('echo Y2 extended >> {0}'.format('/tmp/output')))
__pydsl__.set(ordered=True)
yyy.hello('red', 1)
yyy.hello('green', 2)
yyy.hello('blue', 3)
