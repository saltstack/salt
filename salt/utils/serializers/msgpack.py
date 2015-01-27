# -*- coding: utf-8 -*-
'''
    salt.utils.serializers.msgpack
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Implements MsgPack serializer.
'''

from __future__ import absolute_import
from copy import copy
import logging

from salt.log import setup_console_logger
from salt.utils.serializers import DeserializationError, SerializationError

log = logging.getLogger(__name__)


try:
    # Attempt to import msgpack
    import msgpack
    # There is a serialization issue on ARM and potentially other platforms
    # for some msgpack bindings, check for it
    if msgpack.loads(msgpack.dumps([1, 2, 3]), use_list=True) is None:
        raise ImportError
    available = True
except ImportError:
    # Fall back to msgpack_pure
    try:
        import msgpack_pure as msgpack
    except ImportError:
        # TODO: Come up with a sane way to get a configured logfile
        #       and write to the logfile when this error is hit also
        LOG_FORMAT = '[%(levelname)-8s] %(message)s'
        setup_console_logger(log_format=LOG_FORMAT)
        log.fatal('Unable to import msgpack or msgpack_pure python modules')
        # Don't exit if msgpack is not available, this is to make local mode
        # work without msgpack
        #sys.exit(salt.defaults.exitcodes.EX_GENERIC)
        available = False


if not available:

    def _fail():
        raise RuntimeError('msgpack is not available')

    def _serialize(obj, **options):
        _fail()

    def _deserialize(stream_or_string, **options):
        _fail()

elif msgpack.version >= (0, 2, 0):

    def _serialize(obj, **options):
        if options:
            log.warning('options are currently unusued')
        try:
            return msgpack.dumps(obj)
        except Exception as error:
            raise SerializationError(error)

    def _deserialize(stream_or_string, **options):
        try:
            options.setdefault('use_list', True)
            return msgpack.loads(stream_or_string, **options)
        except Exception as error:
            raise DeserializationError(error)

else:  # msgpack.version < 0.2.0

    def _encoder(obj):
        '''
        Since OrderedDict is identified as a dictionary, we can't make use of
        msgpack custom types, we will need to convert by hand.

        This means iterating through all elements of dictionaries, lists and
        tuples.
        '''
        if isinstance(obj, dict):
            data = [(key, _encoder(value)) for key, value in obj.items()]
            return dict(data)
        elif isinstance(obj, (list, tuple)):
            return [_encoder(value) for value in obj]
        return copy(obj)

    def _decoder(obj):
        return obj

    def _serialize(obj, **options):
        if options:
            log.warning('options are currently unusued')
        try:
            obj = _encoder(obj)
            return msgpack.dumps(obj)
        except Exception as error:
            raise SerializationError(error)

    def _deserialize(stream_or_string, **options):
        options.setdefault('use_list', True)
        try:
            obj = msgpack.loads(stream_or_string)
            return _decoder(obj)
        except Exception as error:
            raise DeserializationError(error)

serialize = _serialize
deserialize = _deserialize

serialize.__doc__ = '''
    Serialize Python data to MsgPack.

    :param obj: the data structure to serialize
    :param options: options given to lower msgpack module.
'''

deserialize.__doc__ = '''
    Deserialize any string of stream like object into a Python data structure.

    :param stream_or_string: stream or string to deserialize.
    :param options: options given to lower msgpack module.
'''
