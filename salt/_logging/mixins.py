"""
    salt._logging.mixins
    ~~~~~~~~~~~~~~~~~~~~

    Logging related mix-ins
"""

import logging
import sys
import weakref


class LoggingProfileMixin:
    """
    Simple mix-in class to add a trace method to python's logging.
    """

    def profile(self, msg, *args, **kwargs):
        self.log(getattr(logging, "PROFILE", 15), msg, *args, **kwargs)


class LoggingTraceMixin:
    """
    Simple mix-in class to add a trace method to python's logging.
    """

    def trace(self, msg, *args, **kwargs):
        self.log(getattr(logging, "TRACE", 5), msg, *args, **kwargs)


class LoggingGarbageMixin:
    """
    Simple mix-in class to add a garbage method to python's logging.
    """

    def garbage(self, msg, *args, **kwargs):
        self.log(getattr(logging, "GARBAGE", 5), msg, *args, **kwargs)


class LoggingMixinMeta(type):
    """
    This class is called whenever a new instance of ``SaltLoggingClass`` is
    created.

    What this class does is check if any of the bases have a `trace()` or a
    `garbage()` method defined, if they don't we add the respective mix-ins to
    the bases.
    """

    def __new__(mcs, name, bases, attrs):
        include_profile = include_trace = include_garbage = True
        bases = list(bases)
        if name == "SaltLoggingClass":
            for base in bases:
                if hasattr(base, "profile"):
                    include_profile = False
                if hasattr(base, "trace"):
                    include_trace = False
                if hasattr(base, "garbage"):
                    include_garbage = False
        if include_profile:
            bases.append(LoggingProfileMixin)
        if include_trace:
            bases.append(LoggingTraceMixin)
        if include_garbage:
            bases.append(LoggingGarbageMixin)
        return super().__new__(mcs, name, tuple(bases), attrs)


class ExcInfoOnLogLevelFormatMixin:
    """
    Logging handler class mixin to properly handle including exc_info on a per logging handler basis
    """

    def format(self, record):
        """
        Format the log record to include exc_info if the handler is enabled for a specific log level
        """
        formatted_record = super().format(record)
        exc_info_on_loglevel = getattr(record, "exc_info_on_loglevel", None)
        exc_info_on_loglevel_formatted = getattr(
            record, "exc_info_on_loglevel_formatted", None
        )
        if exc_info_on_loglevel is None and exc_info_on_loglevel_formatted is None:
            return formatted_record

        # If we reached this far it means the log record was created with exc_info_on_loglevel
        # If this specific handler is enabled for that record, then we should format it to
        # include the exc_info details
        if self.level > exc_info_on_loglevel:
            # This handler is not enabled for the desired exc_info_on_loglevel, don't include exc_info
            return formatted_record

        # If we reached this far it means we should include exc_info
        if (
            not record.exc_info_on_loglevel_instance
            and not exc_info_on_loglevel_formatted
        ):
            # This should actually never occur
            return formatted_record

        if record.exc_info_on_loglevel_formatted is None:
            # Let's cache the formatted exception to avoid recurring conversions and formatting calls
            if (
                self.formatter is None
            ):  # pylint: disable=access-member-before-definition
                self.formatter = logging._defaultFormatter
            record.exc_info_on_loglevel_formatted = self.formatter.formatException(
                record.exc_info_on_loglevel_instance
            )

        # Let's format the record to include exc_info just like python's logging formatted does
        if formatted_record[-1:] != "\n":
            formatted_record += "\n"

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
            formatted_record += record.exc_info_on_loglevel_formatted.decode(
                sys.getfilesystemencoding(), "replace"
            )
        # Reset the record.exc_info_on_loglevel_instance because it might need
        # to "travel" through a multiprocessing process and it might contain
        # data which is not pickle'able
        record.exc_info_on_loglevel_instance = None
        return formatted_record


class MultiprocessingStateMixin:

    # __setstate__ and __getstate__ are only used on spawning platforms.
    def __setstate__(self, state):
        # Deferred to avoid circular imports
        import salt.log.setup

        # If __setstate__ is getting called it means this is running on a
        # new process. Setup logging.
        try:
            salt.log.setup.set_multiprocessing_logging_queue(state["log_queue"])
        except Exception:  # pylint: disable=broad-except
            logging.getLogger(__name__).exception(
                "Failed to run salt.log.setup.set_multiprocessing_logging_queue() on %s",
                self,
            )
        try:
            salt.log.setup.set_multiprocessing_logging_level(state["log_queue_level"])
        except Exception:  # pylint: disable=broad-except
            logging.getLogger(__name__).exception(
                "Failed to run salt.log.setup.set_multiprocessing_logging_level() on %s",
                self,
            )
        try:
            salt.log.setup.setup_multiprocessing_logging(state["log_queue"])
        except Exception:  # pylint: disable=broad-except
            logging.getLogger(__name__).exception(
                "Failed to run salt.log.setup.setup_multiprocessing_logging() on %s",
                self,
            )
        weakref.finalize(self, salt.log.setup.shutdown_multiprocessing_logging)

    def __getstate__(self):
        # Deferred to avoid circular imports
        import salt.log.setup

        # Grab the current multiprocessing logging settings
        log_queue = salt.log.setup.get_multiprocessing_logging_queue()
        log_queue_level = salt.log.setup.get_multiprocessing_logging_level()
        return {
            "log_queue": log_queue,
            "log_queue_level": log_queue_level,
        }
