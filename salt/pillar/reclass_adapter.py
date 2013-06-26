'''
Adapter for reclass.

This file cannot be called reclass.py, because then the module import would
not work. Thanks to the __virtual__ function, however, the plugin still
responds to the name 'reclass'.

More information about reclass: http://github.com/madduck/reclass

It would be desirable to specify the location of reclass in the master config
file. Unfortunately, __opts__ is only made available to the ext_pillar
function, not to the module, so that the import cannot make use of these data,
at least not at the module level, which is needed to set __virtual__
accordingly.
'''
try:
    from reclass.adapters.saltstack import ext_pillar
    __virtual__ = lambda: 'reclass'

except ImportError:
    __virtual__ = lambda: False
