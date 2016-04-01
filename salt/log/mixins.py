# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    salt.log.mixins
    ~~~~~~~~~~~~~~~

    .. versionadded:: 0.17.0

    Some mix-in classes to be used in salt's logging
'''
from __future__ import absolute_import

# Import python libs
import sys
import logging


class LoggingProfileMixIn(object):
    '''
    Simple mix-in class to add a trace method to python's logging.
    '''

    def profile(self, msg, *args, **kwargs):
        self.log(getattr(logging, 'PROFILE', 15), msg, *args, **kwargs)


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
        include_profile = include_trace = include_garbage = True
        bases = list(bases)
        if name == 'SaltLoggingClass':
            for base in bases:
                if hasattr(base, 'trace'):
                    include_trace = False
                if hasattr(base, 'garbage'):
                    include_garbage = False
        if include_profile:
            bases.append(LoggingProfileMixIn)
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


class ExcInfoOnLogLevelFormatMixIn(object):
    '''
    Logging handler class mixin to properly handle including exc_info on a pre logging handler basis
    '''

    def format(self, record):
        '''
        Format the log record to include exc_info if the handler is enabled for a specific log level
        '''
        formatted_record = super(ExcInfoOnLogLevelFormatMixIn, self).format(record)
        exc_info_on_loglevel = getattr(record, 'exc_info_on_loglevel', None)
        if exc_info_on_loglevel is None:
            return formatted_record

        # If we reached this far it means the log record was created with exc_info_on_loglevel
        # If this specific handler is enabled for that record, then we should format it to
        # include the exc_info details
        if self.level > exc_info_on_loglevel:
            # This handler is not enabled for the desired exc_info_on_loglevel, don't include exc_info
            return formatted_record

        # If we reached this far it means we should include exc_info
        if not record.exc_info_on_loglevel_instance:
            # This should actually never occur
            return formatted_record

        if record.exc_info_on_loglevel_formatted is None:
            # Let's cache the formatted exception to avoid recurring conversions and formatting calls
            if self.formatter is None:  # pylint: disable=access-member-before-definition
                self.formatter = logging._defaultFormatter
            record.exc_info_on_loglevel_formatted = self.formatter.formatException(
                record.exc_info_on_loglevel_instance
            )

        # Let's format the record to include exc_info just like python's logging formatted does
        if formatted_record[-1:] != '\n':
            formatted_record += '\n'

        try:
            formatted_record += record.exc_info_on_loglevel_formatted
        except UnicodeError:
            # According to the standard library logging formatter comments:
            #
            #     Sometimes filenames have non-ASCII chars, which can lead
            #     to errors when s is Unicode and record.exc_text is str
            #     See issue 8924.
            #     We also use replace for when there are multiple
            #     encodings, e.g. UTF-8 for the filesystem and latin-1
            #     for a script. See issue 13232.
            formatted_record += record.exc_info_on_loglevel_formatted.decode(sys.getfilesystemencoding(),
                                                                             'replace')

        return formatted_record
