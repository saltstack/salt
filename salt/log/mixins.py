# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    salt.log.mixins
    ~~~~~~~~~~~~~~~

    .. versionadded:: 0.17.0

    Some mix-in classes to be used in salt's logging
'''

# Import python libs
import logging


class LoggingTraceMixIn(object):
    '''
    Simple mix-in class to add a trace method to python's logging.
    '''

    def trace(self, msg, *args, **kwargs):
        self.log(getattr(logging, 'TRACE', 5), msg, *args, **kwargs)


class LoggingGarbageMixIn(object):
    '''
    Simple mix-in class to add a garbage method to python's logging.
    '''

    def garbage(self, msg, *args, **kwargs):
        self.log(getattr(logging, 'GARBAGE', 5), msg, *args, **kwargs)


class LoggingMixInMeta(type):
    '''
    This class is called whenever a new instance of ``SaltLoggingClass`` is
    created.

    What this class does is check if any of the bases have a `trace()` or a
    `garbage()` method defined, if they don't we add the respective mix-ins to
    the bases.
    '''
    def __new__(mcs, name, bases, attrs):
        include_trace = include_garbage = True
        bases = list(bases)
        if name == 'SaltLoggingClass':
            for base in bases:
                if hasattr(base, 'trace'):
                    include_trace = False
                if hasattr(base, 'garbage'):
                    include_garbage = False
        if include_trace:
            bases.append(LoggingTraceMixIn)
        if include_garbage:
            bases.append(LoggingGarbageMixIn)
        return super(LoggingMixInMeta, mcs).__new__(
            mcs, name, tuple(bases), attrs
        )


class NewStyleClassMixIn(object):
    '''
    Simple new style class to make pylint shut up!
    This is required because SaltLoggingClass can't subclass object directly:

        'Cannot create a consistent method resolution order (MRO) for bases'
    '''
