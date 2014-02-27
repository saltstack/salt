# -*- coding: utf-8 -*-
'''
raeting module provides constants and values for the RAET protocol


Packet Data Format.
The data used to initialize a packet is an ordered dict with several fields
most of the fields are shared with the header data format below so only the
unique fields are shown here.

Unique Packet data fields

    sh: source host ip address (ipv4) Default: ''
    sp: source ip port                Default: 7532
    dh: destination host ip address (ipv4) Default: '127.0.0.1'
    dp: destination host ip port           Default 7532

Header Data Format.
The .data in the packet header is an ordered dict  which is used to either
create a packet to transmit
or holds the field from a received packet.
What fields are included in a header is dependent on the header kind.

Header encoding.
    When the head kind is json = 0,then certain optimizations are
    used to minimize the header length.
        The header field keys are two bytes long
        If a header field value is the default then the field is not included
        Lengths are encoded as hex strings
        The flags are encoded as a double char hex string in field 'fg'

header data =
{
    hk: Header kind   (HeadKind) Default 0
    hl: Header length (HeadLen) Default 0

    vn: Version (Version) Default 0

    sd: Source Device ID (SDID)
    dd: Destination Device ID (DDID)
    cf: Correspondent Flag (CrdtFlag) Default 0
    bf: BroadCast Flag (BcstFlag)  Default 0

    si: Session ID (SID) Default 0
    ti: Transaction ID (TID) Default 0
    tk: Transaction Kind (TrnsKind)
    pk: Packet Kind (PcktKind)
    sf: Succedent Flag    (ScdtFlag) Default 0
        Send segments or ordered packets without waiting for interleafed acks

    oi: Order index (OrdrIndx)   Default 0
    dt: Datetime Stamp  (Datetime) Default 0

    sn: Segment Number (SegNum) Default 0
    sc: Segment Count  (SegCnt) Default 1

    pf: Pending Segment Flag  (PendFlag) Default 0
        Not the last segment more pending
    af: All Flag (AllFlag) Default 0
        Resend all segments not just one

    bk: Body kind   (BodyKind) Default 0
    bl: Body length (BodyLen)  Default 0

    ck: Coat kind   (CoatKind) Default 0
    cl: Coat length (CoatLen)  Default 0

    fk: Footer kind   (FootKind) Default 0
    fl: Footer length (FootLen) Default 0

    fg: flags  packed (Flags) Default '00' hs
         2 char Hex string with bits (0, 0, af, pf, 0, sf, bf, cf)
         Zeros are TBD flags
}

Body Data Format
The Body .data is a Mapping

Body Encoding
    When the body kind is json = 0, then the .data is json encoded

Body Decoding


'''

# pylint: skip-file
# pylint: disable=C0103

# Import python libs
from collections import namedtuple, Mapping
try:
    import simplejson as json
except ImportError:
    import json

import struct

# Import ioflo libs
from ioflo.base.odicting import odict

RAET_PORT = 7530
RAET_TEST_PORT = 7531
DEFAULT_SRC_HOST = ''
DEFAULT_DST_HOST = '127.0.0.1'

MAX_HEAD_LEN = 255
JSON_END = '\r\n\r\n'

VERSIONS = odict([('0.1', 0)])
VERSION_NAMES = odict((v, k) for k, v in VERSIONS.iteritems())
VERSION = VERSIONS.values()[0]

HEAD_KINDS = odict([('raet', 0), ('json', 1), ('binary', 2),
                    ('unknown', 255)])
HEAD_KIND_NAMES = odict((v, k) for k, v in HEAD_KINDS.iteritems())  # inverse map
HeadKind = namedtuple('HeadKind', HEAD_KINDS.keys())
headKinds = HeadKind(**HEAD_KINDS)  # headKinds.json is '00'


BODY_KINDS = odict([('nada', 0), ('json', 1), ('raw', 2), ('msgpck', 3),
                    ('unknown', 255)])
BODY_KIND_NAMES = odict((v, k) for k, v in BODY_KINDS.iteritems())  # inverse map
BodyKind = namedtuple('BodyKind', BODY_KINDS.keys())
bodyKinds = BodyKind(**BODY_KINDS)


FOOT_KINDS = odict([('nada', 0), ('nacl', 1), ('sha2', 2),
                     ('crc64', 2), ('unknown', 255)])
FOOT_KIND_NAMES = odict((v, k) for k, v in FOOT_KINDS.iteritems())  # inverse map
FootKind = namedtuple('FootKind', FOOT_KINDS.keys())
footKinds = FootKind(**FOOT_KINDS)

# bytes
FOOT_SIZES = odict([('nada', 0), ('nacl', 64), ('sha2', 0),
                     ('crc64', 8), ('unknown', 0)])
FootSize = namedtuple('FootSize', FOOT_SIZES.keys())
footSizes = FootSize(**FOOT_SIZES)


COAT_KINDS = odict([('nada', 0), ('nacl', 1), ('crc16', 2), ('crc64', 3),
                    ('unknown', 255)])
COAT_KIND_NAMES = odict((v, k) for k, v in COAT_KINDS.iteritems())  # inverse map
CoatKind = namedtuple('CoatKind', COAT_KINDS.keys())
coatKinds = CoatKind(**COAT_KINDS)

# bytes
TAIL_SIZES = odict([('nada', 0), ('nacl', 24), ('crc16', 2), ('crc64', 8),
                    ('unknown', 0)])
TailSize = namedtuple('TailSize', TAIL_SIZES.keys())
tailSizes = TailSize(**TAIL_SIZES)

TRNS_KINDS = odict([('message', 0), ('join', 1), ('accept', 2), ('allow', 3),
                     ('unknown', 255)])
TRNS_KIND_NAMES = odict((v, k) for k, v in TRNS_KINDS.iteritems())  # inverse map
TrnsKind = namedtuple('TrnsKind', TRNS_KINDS.keys())
trnsKinds = TrnsKind(**TRNS_KINDS)

PCKT_KINDS = odict([('message', 0), ('ack', 1), ('nack', 2),
                    ('request', 3), ('response', 4),
                    ('hello', 4), ('cookie', 5), ('initiate', 6),
                    ('unknown', 255)])
PCKT_KIND_NAMES = odict((v, k) for k, v in PCKT_KINDS.iteritems())  # inverse map
PcktKind = namedtuple('PcktKind', PCKT_KINDS.keys())
pcktKinds = PcktKind(**PCKT_KINDS)

HELLO_PACKER = struct.Struct('<64s32s80s24s') #curvecp hello packet body endow trans
COOKIESTUFF_PACKER = struct.Struct('<32sLL24s')
COOKIE_PACKER = struct.Struct('<80s24s')
INITIATESTUFF_PACKER = struct.Struct('<32s48s24s128s')
INITIATE_PACKER = struct.Struct('32s24s248s24s')

# head fields that may be included in json header if not default value
PACKET_DEFAULTS = odict([
                            ('sh', DEFAULT_SRC_HOST),
                            ('sp', RAET_PORT),
                            ('dh', DEFAULT_DST_HOST),
                            ('dp', RAET_PORT),
                            ('hk', 0),
                            ('hl', 0),
                            ('vn', 0),
                            ('sd', 0),
                            ('dd', 0),
                            ('cf', False),
                            ('bf', False),
                            ('si', 0),
                            ('ti', 0),
                            ('tk', 0),
                            ('pk', 0),
                            ('sf', False),
                            ('oi', 0),
                            ('dt', 0),
                            ('sn', 0),
                            ('sc', 1),
                            ('pf', False),
                            ('af', False),
                            ('bk', 0),
                            ('bl', 0),
                            ('ck', 0),
                            ('cl', 0),
                            ('fk', 0),
                            ('fl', 0),
                            ('fg', '00'),
                      ])

PACKET_FIELDS = ['sh', 'sp', 'dh', 'dp',
                 'hk', 'hl', 'vn', 'sd', 'dd', 'cf', 'bf', 'si', 'ti', 'tk', 'pk',
                 'sf', 'oi', 'dt', 'sn', 'sc', 'pf', 'af',
                 'bk', 'bl', 'ck', 'cl', 'fk', 'fl', 'fg']

HEAD_FIELDS = ['hk', 'hl', 'vn', 'sd', 'dd', 'cf', 'bf', 'si', 'ti', 'tk', 'pk',
               'sf', 'oi', 'dt', 'sn', 'sc', 'pf', 'af',
               'bk', 'bl', 'ck', 'cl', 'fk', 'fl', 'fg']

PACKET_FLAGS = ['af', 'pf', 'sf', 'bf', 'cf']
PACKET_FLAG_FIELDS = ['', '', 'af', 'pf', '', 'sf', 'bf', 'cf']


class RaetError(Exception):
    '''
    Exceptions in RAET Protocol processing

       usage:
           emsg = "Invalid device id '{0}'".format(did)
           raise raeting.RaetError(emsg)
    '''
    def __init__(self, message=None):
        self.message = message  # description of error
        super(RaetError, self).__init__(message)

    def __str__(self):
        return "{0}: {1}.\n".format(self.__class__.__name__, self.message)


class StackError(RaetError):
    '''
       Exceptions in RAET stack processing

       Usage:
            emsg = "Invalid device id '{0}'".format(did)
            raise raeting.StackError(emsg)
    '''
    pass

class DeviceError(RaetError):
    '''
       Exceptions in RAET device processing

       Usage:
            emsg = "Invalid device id '{0}'".format(did)
            raise raeting.DeviceError(emsg)
    '''
    pass

class TransactionError(RaetError):
    '''
       Exceptions in RAET transaction processing

       Usage:
            emsg = "Invalid device id '{0}'".format(did)
            raise raeting.TransactionError(emsg)
    '''
    pass

class PacketError(RaetError):
    '''
       Exceptions in RAET packet processing

       Usage:
            emsg = "Invalid device id '{0}'".format(did)
            raise raeting.PacketError(emsg)
    '''
    pass
