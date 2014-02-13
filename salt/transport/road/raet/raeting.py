# -*- coding: utf-8 -*-
#pylint: skip-file
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
    hk: header kind   (HeadKind) Default 0
    hl: header length (HeadLen) Default 0

    vn: version (Version) Default 0

    sd: Source Device ID (SDID)
    dd: Destination Device ID (DDID)
    cf: Corresponder Flag (CrdrFlag) Default 0
    bf: BroadCast Flag (BcstFlag)  Default 0

    si: Session ID (SID) Default 0
    ti: Transaction ID (TID) Default 0
    sk: Service Kind (SrvcKind)
    pk: Packet Kind (PcktKind)
    sf: Succedent Flag    (ScdtFlag) Default 0
        Send segments or ordered packets without waiting for interleafed acks

    oi: order index (OrdrIndx)   Default 0
    dt: Datetime Stamp  (Datetime) Default 0

    sn: Segment Number (SegNum) Default 0
    sc: Segment Count  (SegCnt) Default 1

    pf: Pending Segment Flag  (PendFlag) Default 0
        Not the last segment more pending
    af: All Flag (AllFlag) Default 0
        Resend all segments not just one

    nk: Neck header kind   (NeckKind) Default 0
    nl: Neck header length (NeckLen) Default 0

    bk: body kind   (BodyKind) Default 0
    bl: body length (BodyLen)  Default 0

    tk: tail kind   (TailKind) Default 0
    tl: tail length (TailLen)  Default 0

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

# pylint: disable=C0103

# Import python libs
from collections import namedtuple, Mapping
try:
    import simplejson as json
except ImportError:
    import json

# Import ioflo libs
from ioflo.base.odicting import odict

RAET_PORT = 7530
RAET_TEST_PORT = 7531

MAX_HEAD_LEN = 255
JSON_END = '\r\n\r\n'

HEAD_KINDS = odict([('raet', 0), ('json', 1), ('binary', 2),
                    ('unknown', 255)])
HEAD_KIND_NAMES = odict((v, k) for k, v in HEAD_KINDS.iteritems())  # inverse map
HeadKind = namedtuple('HeadKind', HEAD_KINDS.keys())
headKinds = HeadKind(**HEAD_KINDS)  # headKinds.json is '00'

VERSIONS = odict([('0.1', 0)])
VERSION_NAMES = odict((v, k) for k, v in VERSIONS.iteritems())

VERSION = VERSIONS.values()[0]

NECK_KINDS = odict([('nada', 0), ('nacl', 1), ('sha2', 2),
                     ('crc64', 2), ('unknown', 255)])
NECK_KIND_NAMES = odict((v, k) for k, v in NECK_KINDS.iteritems())  # inverse map
NeckKind = namedtuple('NeckKind', NECK_KINDS.keys())
neckKinds = NeckKind(**NECK_KINDS)

# bytes
NECK_SIZES = odict([('nada', 0), ('nacl', 64), ('sha2', 0),
                     ('crc64', 8), ('unknown', 0)])
NeckSize = namedtuple('NeckSize', NECK_SIZES.keys())
neckSizes = NeckSize(**NECK_SIZES)

BODY_KINDS = odict([('nada', 0), ('json', 1), ('msgpck', 1), ('unknown', 255)])
BODY_KIND_NAMES = odict((v, k) for k, v in BODY_KINDS.iteritems())  # inverse map
BodyKind = namedtuple('BodyKind', BODY_KINDS.keys())
bodyKinds = BodyKind(**BODY_KINDS)

TAIL_KINDS = odict([('nada', 0), ('nacl', 1), ('crc16', 2), ('crc64', 3),
                    ('unknown', 255)])
TAIL_KIND_NAMES = odict((v, k) for k, v in TAIL_KINDS.iteritems())  # inverse map
TailKind = namedtuple('TailKind', TAIL_KINDS.keys())
tailKinds = TailKind(**TAIL_KINDS)

# bytes
TAIL_SIZES = odict([('nada', 0), ('nacl', 8), ('crc16', 2), ('crc64', 8),
                    ('unknown', 0)])
TailSize = namedtuple('TailSize', TAIL_SIZES.keys())
tailSizes = TailSize(**TAIL_SIZES)

SERVICE_KINDS = odict([('fireforget', 0), ('ackretry', 1), (
    'unknown', 255)])
SERVICE_KIND_NAMES = odict((v, k) for k, v in SERVICE_KINDS.iteritems())  # inverse map
ServiceKind = namedtuple('ServiceKind', SERVICE_KINDS.keys())
serviceKinds = ServiceKind(**SERVICE_KINDS)

PACKET_KINDS = odict([('data', 0), ('ack', 1), ('nack', 2),
                      ('join', 3), ('acceptAck', 4), ('accept', 5),
                      ('unknown', 255)])
PACKET_KIND_NAMES = odict((v, k) for k, v in PACKET_KINDS.iteritems())  # inverse map
PacketKind = namedtuple('PacketKind', PACKET_KINDS.keys())
packetKinds = PacketKind(**PACKET_KINDS)


# head fields that may be included in json header if not default value
PACKET_DEFAULTS = odict([
                            ('sh', ''),
                            ('sp', 7530),
                            ('dh', '127.0.0.1'),
                            ('dp', 7530),
                            ('hk', 0),
                            ('hl', 0),
                            ('vn', 0),
                            ('sd', 0),
                            ('dd', 0),
                            ('cf', 0),
                            ('bf', 0),
                            ('si', 0),
                            ('ti', 0),
                            ('sk', 0),
                            ('pk', 0),
                            ('sf', 0),
                            ('oi', 0),
                            ('dt', 0),
                            ('sn', 0),
                            ('sc', 1),
                            ('pf', 0),
                            ('af', 0),
                            ('nk', 0),
                            ('nl', 0),
                            ('bk', 0),
                            ('bl', 0),
                            ('tk', 0),
                            ('tl', 0),
                            ('fg', '00'),
                      ])

PACKET_FIELDS = ['sh', 'sp', 'dh', 'dp',
                 'hk', 'hl', 'vn', 'sd', 'dd', 'cf', 'bf', 'si', 'ti', 'sk', 'pk',
                 'sf', 'oi', 'dt', 'sn', 'sc', 'pf', 'af',
                 'nk', 'nl', 'bk', 'bl', 'tk', 'tl', 'fg']

HEAD_FIELDS = ['hk', 'hl', 'vn', 'sd', 'dd', 'cf', 'bf', 'si', 'ti', 'sk', 'pk',
               'sf', 'oi', 'dt', 'sn', 'sc', 'pf', 'af',
               'nk', 'nl', 'bk', 'bl', 'tk', 'tl', 'fg']

PACKET_FLAGS = ['af', 'pf', 'sf', 'bf', 'cf']
PACKET_FLAG_FIELDS = ['', '', 'af', 'pf', '', 'sf', 'bf', 'cf']


class RaetError(Exception):
    '''
    Used to indicate error in RAET Protocol

       usage:
       msg = "Invalid device id '{0}'".format(did)
       raise raeting.RaetError(msg)
    '''
    def __init__(self, message=None):
        self.message = message  # description of error
        super(RaetError, self).__init__(message)

    def __str__(self):
        return "{0}: {1}.\n".format(self.__class__.__name__, self.message)


def defaultData(data=None):
    '''
    Returns defaulted data
    '''
    if data is None:
        data = odict()
    for part in DATA_PARTS:  # make sure all parts in data
        if part not in data:
            data[part] = odict()
    if 'pack' not in data:
        data['pack'] = ''
    return data


def updateMissing(kit, defaults):
    '''
    Update kit dict with item from default if item missing in kit
    '''
    for k, v in defaults.items():
        if k not in kit:
            kit[k] = v


def packPacket(data):
    '''
    Uses data to create packed version and assigns to pack field in data
    Also returns packed packet
    '''
    meta = data['meta']
    head = data['head']
    neck = data['neck']
    body = data['body']
    tail = data['tail']

    packBody(meta, body)
    packTail(meta, body, tail)
    packHead(meta, head)
    packNeck(meta, head, neck)
    data['pack'] = '{0}{1}{2}{3}'.format(head['pack'], neck['pack'], body['pack'], tail['pack'])
    return data['pack']


def packBody(meta, body):
    '''
    Uses meta, and body data to create packed version updates fields in body
    '''
    body['pack'] = ''
    if meta.get('bk') == bodyKinds.json:
        kit = body.get('raw', '') or body.get('data', {})
        packed = json.dumps(kit, separators=(',', ':'))
        body['pack'] = packed
    meta['bl'] = len(body['pack'])


def packTail(meta, body, tail):
    '''
    Uses meta, and body data to create packed version of tail and updates meta and tail
    '''
    tail['pack'] = ''
    if meta.get('tk') == tailKinds.nada:
        pass
    meta['tl'] = len(tail['pack'])


def packHead(meta, head):
    '''
    Uses meta and head data to create packed version and assigns to pack field in head
    '''
    meta['error'] = ''
    head['pack'] = ''
    if head.get('hk') == headKinds.json:
        kit = odict()
        for field in META_LEN_FIELDS:
            head[field] = meta[field]
        for field in META_KIND_FIELDS:
            head[field] = meta[field]
        for k, v in HEAD_DEFAULTS.items():
            if v is None:
                kit[k] = head[k]
            else:
                if head[k] != v:
                    kit[k] = head[k]

        kit['hl'] = '00'  # need hex string so fixed length and jsonable
        packed = json.dumps(kit, separators=(',', ':'), encoding='ascii',)
        packed = '{0}{1}'.format(packed, JSON_END)
        hl = len(packed)
        if hl > MAX_HEAD_LEN:
            meta['error'] = "Head length of {0}, exceeds max of {1}".format(hl, MAX_HEAD_LEN)
            meta['hl'] = 0
            return
        meta['hl'] = head['hl'] = hl
        #subsitute true length converted to 2 byte hex string
        packed = packed.replace('"hl":"00"', '"hl":"{0}"'.format("{0:02x}".format(hl)[-2:]), 1)
        head['pack'] = packed


def packNeck(meta, head, neck):
    '''
    Signs the head and puts auth signature into neck
    '''
    neck['pack'] = ''
    if meta.get('nk') == neckKinds.nada:
        pass
    meta['nl'] = len(neck['pack'])


def parsePacket(data):
    '''
    Parses raw packet data in data['pack'] and updates data
    '''
    meta = data['meta']
    head = data['head']
    neck = data['neck']
    body = data['body']
    tail = data['tail']
    pack = data['pack']

    updateMissing(meta, META_DEFAULTS)

    meta['error'] = ''

    rest = parseHead(pack, meta, head)
    rest = parseNeck(rest, meta, neck)
    if not vouchHead(meta, head, neck):
        return
    rest = parseBody(rest, meta, body)
    rest = parseTail(rest, meta, tail)
    if not verifyBody(meta, head, tail):
        return

    return rest


def parseHead(pack, meta, head):
    '''
    Parses and removes head from pack and returns remainder
    updates meta and head dicts:
    '''
    meta['error'] = ''
    #need to test for Header type and version
    if pack.startswith('{"hk":0,') and JSON_END in pack:  # json header
        meta['hk'] = headKinds.json
        front, sep, back = pack.partition(JSON_END)
        pack = back
        head['pack'] = "{0}{1}".format(front, sep)
        meta['hl'] = len(head['pack'])

        head.update(HEAD_DEFAULTS)
        kit = json.loads(front,
                         encoding='ascii',
                         object_pairs_hook=odict)
        head.update(kit)

        hl = int(head['hl'], 16)
        if hl != meta['hl']:
            meta['error'] = 'Actual head length does not match head field value.'

        if head['hk'] != meta['hk']:
            meta['error'] = 'Actual head kind does not match head field value.'

        for field in META_LEN_FIELDS:
            meta[field] = head[field]
        for field in META_KIND_FIELDS:
            meta[field] = head[field]

    else:  # notify unrecognizible packet
        meta['hl'] = 0
        meta['hk'] = headKinds.unknown
        meta['error'] = "Unrecognizible packet head."

    return pack


def parseNeck(pack, meta, neck):
    '''
    Parses and removes neck from pack and returns remainder
    updates meta and neck dicts.
    '''
    meta['error'] = ''
    nl = meta.get('nl', 0)
    neck['pack'] = pack[:nl]
    pack = pack[nl:]

    if meta.get('nk') == neckKinds.nada:
        pass

    else:  # notify unrecognizible packet
        meta['nl'] = 0
        meta['nk'] = neckKinds.unknown
        meta['error'] = "Unrecognizible packet neck."

    return pack


def parseBody(pack, meta, body):
    '''
    Parses and removes head from pack and returns remainder
    updates meta and body dicts:
    '''
    meta['error'] = ''
    body['raw'] = ''
    bl = meta.get('bl', 0)
    body['pack'] = pack[:bl]
    pack = pack[bl:]

    if meta.get('bk') == bodyKinds.json:
        if bl:
            kit = json.loads(body['pack'], object_pairs_hook=odict)
            if isinstance(kit, Mapping):
                body['data'] = kit
            else:
                body['raw'] = kit

    else:  # notify unrecognizible packet
        meta['bl'] = 0
        meta['bk'] = bodyKinds.unknown
        meta['error'] = 'Unrecognizible packet body.'

    return pack


def parseTail(pack, meta, tail):
    '''
    Parses and removes tail from pack and returns remainder
    updates meta and tail dicts.
    '''
    meta['error'] = ''
    tl = meta.get('tl', 0)
    tail['pack'] = pack[:tl]
    pack = pack[tl:]

    if meta.get('tk') == tailKinds.nada:
        pass

    else:  # notify unrecognizible packet
        meta['tl'] = 0
        meta['tk'] = tailKinds.unknown
        meta['error'] = 'Unrecognizible packet tail.'

    return pack


def vouchHead(meta, head, neck):
    '''
    Uses signature in neck to vouch for (authenticate) head
    '''
    #meta['error'] = "Head failed authentication."
    return True


def verifyBody(meta, body, tail):
    '''
    Uses tail to verify body does not have errors
    '''
    #meta['error'] = "Body failed verification."
    return True
