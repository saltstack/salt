# -*- coding: utf-8 -*-
#pylint: skip-file
'''
packeting module provides classes for Raet packets

'''

# Import python libs
from collections import Mapping
try:
    import simplejson as json
except ImportError:
    import json

# Import ioflo libs
from ioflo.base.odicting import odict
from ioflo.base.aiding import packByte, unpackByte

from . import raeting

class Part(object):
    '''
    Base class for parts of a RAET packet
    Should be subclassed
    '''

    def __init__(self, packet=None, kind=None, **kwa):
        '''
        Setup Part instance
        '''
        self.packet = packet  # Packet this Part belongs too
        self.kind = kind  # part kind
        self.packed = ''

    def __len__(self):
        '''
        Returns the length of .packed
        '''
        return len(self.packed)

    @property
    def size(self):
        '''
        Property is the length of this Part
        '''
        return self.__len__()

class Head(Part):
    '''
    RAET protocol packet header class
    Manages the header portion of a packet
    '''
    def __init__(self, **kwa):
        '''
        Setup Head instance
        '''
        super(Head, self).__init__(**kwa)

class TxHead(Head):
    '''
    RAET protocl transmit packet header class
    '''
    def pack(self):
        '''
        Composes .packed, which is the packed form of this part
        '''
        self.packed = ''
        self.kind = self.packet.data['hk']
        data = self.packet.data  # for speed

        data['pk'] = self.packet.kind
        data['bk'] = self.packet.body.kind
        data['bl'] = self.packet.body.size
        data['ck'] = self.packet.coat.kind
        data['cl'] = self.packet.coat.size
        data['fk'] = self.packet.foot.kind
        data['fl'] = self.packet.foot.size

        data['fg'] = "{:02x}".format(self.packFlags())

        # kit always includes header kind and length fields
        kit = odict([('hk', self.kind), ('hl', 0)])
        for k, v in raeting.PACKET_DEFAULTS.items():  # include if not equal to default
            if ((k in raeting.HEAD_FIELDS) and
                (k not in raeting.PACKET_FLAGS) and
                (data[k] != v)):
                kit[k] = data[k]

        if self.kind == raeting.headKinds.json:
            kit['hl'] = '00'  # need hex string so fixed length and jsonable
            packed = json.dumps(kit, separators=(',', ':'), encoding='ascii',)
            packed = '{0}{1}'.format(packed, raeting.JSON_END)
            hl = len(packed)
            if hl > raeting.MAX_HEAD_LEN:
                emsg = "Head length of {0}, exceeds max of {1}".format(hl, MAX_HEAD_LEN)
                raise raeting.PacketError(emsg)

            #subsitute true length converted to 2 byte hex string
            self.packed = packed.replace('"hl":"00"', '"hl":"{0}"'.format("{0:02x}".format(hl)[-2:]), 1)

    def packFlags(self):
        '''
        Packs all the flag fields into a single two char hex string
        '''
        values = []
        for field in raeting.PACKET_FLAG_FIELDS:
            values.append(1 if self.packet.data.get(field, 0) else 0)
        return packByte(format='11111111', fields=values)

class RxHead(Head):
    '''
    RAET protocl receive packet header class
    '''
    def parse(self):
        '''
        From .packed.packed, Detects head kind. Unpacks head. Parses head and updates
        .packet.data
        Raises PacketError if failure occurs
        '''
        self.packed = ''
        data = self.packet.data  # for speed
        packed = self.packet.packed  # for speed
        if packed.startswith('{"hk":1,') and raeting.JSON_END in packed:  # json header
            self.kind = raeting.headKinds.json
            front, sep, back = packed.partition(raeting.JSON_END)
            self.packed = "{0}{1}".format(front, sep)
            kit = json.loads(front,
                             encoding='ascii',
                             object_pairs_hook=odict)
            data.update(kit)
            if 'fg' in data:
                self.unpackFlags(data['fg'])

            if data['hk'] != self.kind:
                emsg = 'Recognized head kind does not match head field value.'
                raise raeting.PacketError(emsg)

            hl = int(data['hl'], 16)
            if hl != self.size:
                emsg = 'Actual head length does not match head field value.'
                raise raeting.PacketError(emsg)
            data['hl'] = hl

        else:  # notify unrecognizible packet head
            self.kind = raeting.headKinds.unknown
            emsg = "Unrecognizible packet head."
            raise raeting.PacketError(emsg)

    def unpackFlags(self, flags):
        '''
        Unpacks all the flag fields from a single two char hex string
        '''
        values = unpackByte(format='11111111', byte=int(flags, 16), boolean=True)
        for i, field in enumerate(raeting.PACKET_FLAG_FIELDS):
            if field in self.packet.data:
                self.packet.data[field] = values[i]

class Body(Part):
    '''
    RAET protocol packet body class
    Manages the messsage  portion of the packet
    '''
    def __init__(self, data=None, **kwa):
        '''
        Setup Body instance
        '''
        super(Body, self).__init__(**kwa)
        if data is None:
            data = odict()
        self.data = data

class TxBody(Body):
    '''
    RAET protocol tx packet body class
    '''
    def pack(self):
        '''
        Composes .packed, which is the packed form of this part
        '''
        self.packed = ''
        self.kind = self.packet.data['bk']
        if self.kind == raeting.bodyKinds.json:
            self.packed = json.dumps(self.data, separators=(',', ':'))

        if self.kind == raeting.bodyKinds.raw:
            self.packed = self.data # data is already formatted string

class RxBody(Body):
    '''
    RAET protocol rx packet body class
    '''
    def parse(self):
        '''
        Parses body. Assumes already unpacked.
        Results in updated .data
        '''
        self.kind = self.packet.data['bk']

        if self.kind not in raeting.BODY_KIND_NAMES:
            self.kind = raeting.bodyKinds.unknown
            emsg = "Unrecognizible packet body."
            raise raeting.PacketError(emsg)

        if self.size != self.packet.data['bl']:
            emsg = ("Mismatching body size '{0}' and data length '{1}'"
                   "".format(self.size, self.packet.data['bl']))
            raise raeting.PacketError(emsg)

        self.data = odict()

        if self.kind == raeting.bodyKinds.json:
            if self.packed:
                kit = json.loads(self.packed, object_pairs_hook=odict)
                if not isinstance(kit, Mapping):
                    emsg = "Packet body not a mapping."
                    raise raeting.PacketError(emsg)
                self.data = kit

        if self.kind == raeting.bodyKinds.raw:
            self.data = self.packed # return as string

        elif self.kind == raeting.bodyKinds.nada:
            pass

class Coat(Part):
    '''
    RAET protocol packet coat class
    Supports enapsulated encrypt/decrypt of body portion of packet
    '''
    def __init__(self, **kwa):
        ''' Setup Coat instance'''
        super(Coat, self).__init__(**kwa)

class TxCoat(Coat):
    '''
    RAET protocol tx packet coat class
    '''
    def pack(self):
        '''
        Composes .packed, which is the packed form of this part
        '''
        self.packed = ''
        self.kind = self.packet.data['ck']

        if self.kind == raeting.coatKinds.nacl:
            msg = self.packet.body.packed
            cipher, nonce = self.packet.encrypt(msg)
            self.packed = "".join([cipher, nonce])

        if self.kind == raeting.coatKinds.nada:
            self.packed = self.packet.body.packed

class RxCoat(Coat):
    '''
    RAET protocol rx packet coat class
    '''
    def parse(self):
        '''
        Parses coat. Assumes already unpacked.
        '''
        self.kind = self.packet.data['ck']

        if self.kind not in raeting.COAT_KIND_NAMES:
            self.kind = raeting.coatKinds.unknown
            emsg = "Unrecognizible packet coat."
            raise raeting.PacketError(emsg)

        if self.kind == raeting.coatKinds.nacl:
            tl = raeting.tailSizes.nacl # nonce length

            cipher = self.packed[:-tl]
            nonce = self.packed[-tl:]
            msg = self.packet.decrypt(cipher, nonce)
            self.packet.body.packed = msg

        if self.kind == raeting.coatKinds.nada:
            self.packet.body.packed = self.packed


class Foot(Part):
    '''
    RAET protocol packet foot class
    Manages the signing or authentication of the packet
    '''
    def __init__(self, **kwa):
        '''
        Setup Foot instance
        '''
        super(Foot, self).__init__(**kwa)

class TxFoot(Foot):
    '''
    RAET protocol transmit packet foot class
    '''

    def pack(self):
        '''
        Composes .packed, which is the packed form of this part
        '''
        self.packed = ''
        self.kind = self.packet.data['fk']

        if self.kind not in raeting.FOOT_KIND_NAMES:
            self.kind = raeting.footKinds.unknown
            emsg = "Unrecognizible packet foot."
            raise raeting.PacketError(emsg)

        if self.kind == raeting.footKinds.nacl:
            self.packed = "".rjust(raeting.footSizes.nacl, '\x00')

        elif self.kind == raeting.footKinds.nada:
            pass

    def sign(self):
        '''
        Compute signature on packet.packed and update packet.packet with signature
        '''
        if self.kind not in raeting.FOOT_KIND_NAMES:
            self.kind = raeting.footKinds.unknown
            emsg = "Unrecognizible packet foot."
            raise raeting.PacketError(emsg)

        if self.kind == raeting.footKinds.nacl:
            #blank = "".rjust(raeting.footSizes.nacl, '\x00')
            #msg = "".join([self.packet.head.packed, self.packet.coat.packed, blank])
            self.packed = self.packet.signature(self.packet.packed)

        elif self.kind == raeting.footKinds.nada:
            pass

class RxFoot(Foot):
    '''
    RAET protocol receive packet foot class
    '''
    def parse(self):
        '''
        Parses foot. Assumes foot already unpacked
        '''
        self.kind = self.packet.data['fk']

        if self.kind not in raeting.FOOT_KIND_NAMES:
            self.kind = raeting.footKinds.unknown
            emsg = "Unrecognizible packet foot."
            raise raeting.PacketError(emsg)

        if self.kind == raeting.footKinds.nacl:
            if self.size != raeting.footSizes.nacl:
                emsg = ("Actual foot size '{0}' does not match "
                    "kind size '{1}'".format(self.size, raeting.footSizes.nacl))
                raise raeting.PacketError(emsg)

            signature = self.packed
            blank = "".rjust(raeting.footSizes.nacl, '\x00')
            msg = "".join([self.packet.head.packed, self.packet.coat.packed, blank])
            if not self.packet.verify(signature, msg):
                emsg = "Failed verification"
                raise raeting.PacketError(emsg)

        if self.kind == raeting.footKinds.nada:
            pass

class Packet(object):
    '''
    RAET protocol packet object
    '''
    def __init__(self, stack=None, kind=None):
        ''' Setup Packet instance. Meta data for a packet. '''
        self.stack = stack
        self.kind = kind or raeting.PACKET_DEFAULTS['pk']
        self.packed = ''  # packed string
        self.segments = [] # subpackets when segmented
        self.data = odict(raeting.PACKET_DEFAULTS)

    @property
    def size(self):
        '''
        Property is the length of the .packed of this Packet
        '''
        return len(self.packed)

    def refresh(self, data=None):
        '''
        Refresh .data to defaults and update if data
        '''
        self.data = odict(raeting.PACKET_DEFAULTS)
        if data:
            self.data.update(data)
        return self  # so can method chain

class TxPacket(Packet):
    '''
    RAET Protocol Transmit Packet object
    '''
    def __init__(self, embody=None, data=None, **kwa):
        '''
        Setup TxPacket instance
        '''
        super(TxPacket, self).__init__(**kwa)
        self.head = TxHead(packet=self)
        self.body = TxBody(packet=self, data=embody)
        self.coat = TxCoat(packet=self)
        self.foot = TxFoot(packet=self)
        if data:
            self.data.update(data)

    @property
    def index(self):
        '''
        Property is transaction tuple (rf, ld, rd, si, ti, bf,)
        '''
        data = self.data
        return ((data['cf'], data['sd'], data['dd'], data['si'], data['ti'], data['bf']))

    def signature(self, msg):
        '''
        Return signature resulting from signing msg
        '''
        return (self.stack.device.signer.signature(msg))

    def sign(self):
        '''
        Sign packet with foot
        '''
        self.foot.sign()
        self.packed = ''.join([self.head.packed, self.coat.packed, self.foot.packed])

    def encrypt(self, msg):
        '''
        Return (cipher, nonce) duple resulting from encrypting message
        with short term keys
        '''
        remote = self.stack.devices[self.data['dd']]
        return (remote.privee.encrypt(msg, remote.publee.key))

    def pack(self):
        '''
        Pack the parts of the packet and then the full packet into .packed
        '''
        self.body.pack()
        self.coat.pack()
        self.foot.pack()
        self.head.pack()
        self.packed = ''.join([self.head.packed, self.coat.packed, self.foot.packed])
        self.sign()

class RxPacket(Packet):
    '''
    RAET Protocol Receive Packet object
    '''
    def __init__(self, packed=None, **kwa):
        '''
        Setup RxPacket instance
        '''
        super(RxPacket, self).__init__(**kwa)
        self.head = RxHead(packet=self)
        self.body = RxBody(packet=self)
        self.coat = RxCoat(packet=self)
        self.foot = RxFoot(packet=self)
        self.packed = packed or ''

    @property
    def index(self):
        '''
        Property is transaction tuple (rf, ld, rd, si, ti, bf,)
        '''
        data = self.data
        return ((not data['cf'], data['dd'], data['sd'], data['si'], data['ti'], data['bf']))

    def verify(self, signature, msg):
        '''
        Return result of verifying msg with signature
        '''
        return (self.stack.devices[self.data['sd']].verfer.verify(signature, msg))

    def decrypt(self, cipher, nonce):
        '''
        Return msg resulting from decrypting cipher and nonce
        with short term keys
        '''
        remote = self.stack.devices[self.data['sd']]
        return (self.stack.device.privee.decrypt(cipher, nonce, remote.publee, key))

    def unpack(self, packed=None):
        '''
        Unpacks the foot, body, and coat parts of .packed
        Assumes that the lengths of the parts are valid in .data as would be
        the case after successfully parsing the head section
        '''
        hl = self.data['hl']
        cl = self.data['cl']
        bl = self.data['bl']
        fl = self.data['fl']

        ck = self.data['ck']
        if ck == raeting.coatKinds.nada and cl != bl: #not encrypted so coat and body the same
            emsg = ("Coat kind '{0}' incompatible with coat length '{0}' "
                          "and body length '{2}'".format(cl, cl, bl))
            raise raeting.PacketError(emsg)

        pl = hl + cl + fl
        if self.size != pl:
            emsg = ("Packet length '{0}' does not equal sum of the parts"
                          " '{1}'".format(self.size, pl))
            raise raeting.PacketError(emsg)

        self.coat.packed = self.packed[hl:hl+cl]
        self.foot.packed = self.packed[hl+cl:]

    def parse(self, packed=None):
        '''
        Parses raw packet completely
        Result is .data and .body.data
        Raises PacketError exception If failure
        '''
        self.parseOuter(packed=packed)
        self.parseInner()

    def parseOuter(self, packed=None):
        '''
        Parses raw packet head from packed if provided or .packed otherwise
        Deserializes head
        Unpacks rest of packet.
        Parses foot (signature) if given and verifies signature
        Returns False if not verified Otherwise True
        Result is .data
        Raises PacketError exception If failure
        '''
        if packed:
            self.packed = packed
        if not self.packed:
            emsg = "Packed empty, nothing to parse."
            raise raeting.PacketError(emsg)

        self.head.parse()

        if self.data['vn'] not in raeting.VERSIONS.values():
            emsg = ("Received incompatible version '{0}'"
                    "version '{1}'".format(self.data['vn']))
            raise raeting.PacketError(emsg)

        self.unpack()
        self.foot.parse()

    def parseInner(self):
        '''
        Assumes the head as already been parsed so self.data is valid
        Assumes packet as already been unpacked
        Assumes foot signature has already been verified if any
        Parses coat if given and decrypts enclosed body
        Parses decrypted body and deserializes
        Returns True if decrypted deserialize successful Otherwise False
        Result is .body.data and .data
        Raises PacketError exception If failure
        '''
        self.coat.parse()
        self.body.parse()
