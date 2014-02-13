# -*- coding: utf-8 -*-
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
        Composes and returns .packed, which is the packed form of this part
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
                self.packet.error = "Head length of {0}, exceeds max of {1}".format(hl, MAX_HEAD_LEN)
                return self.packed
            #subsitute true length converted to 2 byte hex string
            self.packed = packed.replace('"hl":"00"', '"hl":"{0}"'.format("{0:02x}".format(hl)[-2:]), 1)

        return self.packed

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
        Returns False and updates .packet.error if failure occurs
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
                self.packet.error = 'Recognized head kind does not match head field value.'
                return False

            hl = int(data['hl'], 16)
            if hl != self.size:
                self.packet.error = 'Actual head length does not match head field value.'
            data['hl'] = hl

        else:  # notify unrecognizible packet head
            self.kind = raeting.headKinds.unknown
            self.packet.error = "Unrecognizible packet head."
            return False

        return True

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
        self.data = data or odict()

class TxBody(Body):
    '''
    RAET protocol tx packet body class
    '''
    def pack(self):
        '''
        Composes and returns .packed, which is the packed form of this part
        '''
        self.packed = ''
        self.kind = self.packet.data['bk']
        if self.kind == raeting.bodyKinds.json:
            self.packed = json.dumps(self.data, separators=(',', ':'))
        return self.packed

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
            self.packet.error = "Unrecognizible packet body."
            return False

        if self.size != self.packet.data['bl']:
            msg = ("Mismatching body size '{0}' and data length '{1}'"
                   "".format(self.size, self.packet.data['bl']))
            self.packet.error = msg
            return False

        self.data = odict()

        if self.kind == raeting.bodyKinds.json:
            if self.packed:
                kit = json.loads(self.packed, object_pairs_hook=odict)
                if not isinstance(kit, Mapping):
                    self.packet.error = "Packet body not a mapping."
                    return False
                self.data = kit

        elif self.kind == raeting.bodyKinds.nada:
            pass

        return True

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
        Composes and returns .packed, which is the packed form of this part
        '''
        self.packed = ''
        self.kind = self.packet.data['ck']

        if self.kind == raeting.coatKinds.nacl:
            msg = self.packet.body.packed
            cipher, nonce = self.packet.transaction.encrypt(msg)
            self.packed = "".join([cipher, nonce])

        if self.kind == raeting.coatKinds.nada:
            self.packed = self.packet.body.packed

        return self.packed

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
            self.packet.error = "Unrecognizible packet coat."
            return False

        if self.kind == raeting.coatKinds.nacl:
            tl = raeting.tailSizes.nacl # nonce length

            cipher = self.packed[:-tl]
            nonce = self.packed[-tl:]
            msg = self.packet.transaction.decrypt(cipher, nonce)
            self.packet.body.packed = msg

        if self.kind == raeting.coatKinds.nada:
            self.packet.body.packed = self.packed

        return True

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
        Composes and returns .packed, which is the packed form of this part
        '''
        self.packed = ''
        self.kind = self.packet.data['fk']

        if self.kind not in raeting.FOOT_KIND_NAMES:
            self.kind = raeting.footKinds.unknown
            self.packet.error = "Unrecognizible packet foot."
            return self.packed

        if self.kind == raeting.footKinds.nacl:
            blank = "".rjust(raeting.footSizes.nacl, '\x00')
            msg = "".join([self.packet.head.packed, self.packet.coat.packed, blank])
            self.packed = self.packet.transaction.signature(msg)

        elif self.kind == raeting.footKinds.nada:
            pass

        return self.packed


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
            self.packet.error = "Unrecognizible packet foot."
            return False

        if self.kind == raeting.footKinds.nacl:
            if self.size != raeting.footSizes.nacl:
                self.packet.error = ("Actual foot size '{0}' does not match "
                    "kind size '{1}'".format(self.size, raeting.footSizes.nacl))
                return False

            signature = self.packed
            blank = "".rjust(raeting.footSizes.nacl, '\x00')
            msg = "".join([self.packet.head.packed, self.packet.coat.packed, blank])
            return self.packet.transaction.verify(signature, msg)

        if self.kind == raeting.footKinds.nada:
            pass

        return True


class Packet(object):
    '''
    RAET protocol packet object
    '''
    def __init__(self, transaction=None, kind=None):
        ''' Setup Packet instance. Meta data for a packet. '''
        self.transaction = transaction
        self.kind = kind or raeting.PACKET_DEFAULTS['pk']
        self.packed = ''  # packed string
        self.error = ''
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

    def pack(self):
        '''
        Pack the parts of the packet and then the full packet
        '''
        self.error = ''
        self.body.pack()
        self.coat.pack()
        self.foot.pack()
        self.head.pack()
        self.packed = ''.join([self.head.packed, self.coat.packed, self.foot.packed])
        self.sign()
        return self.packed

    def sign(self):
        '''
        Sign .packed using foot
        '''
        return True

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
            self.error = ("Coat kind '{0}' incompatible with coat length '{0}' "
                          "and body length '{2}'".format(cl, cl, bl))
            return False

        pl = hl + cl + fl
        if self.size != pl:
            self.error = ("Packet length '{0}' does not equal sum of the parts"
                          " '{1}'".format(self.size, pl))
            return False

        self.coat.packed = self.packed[hl:hl+cl]
        self.foot.packed = self.packed[hl+cl:]
        return True

    def parse(self, packed=None):
        '''
        Parses raw packet completely
        Result is .data and .body.data
        '''
        if not self.parseOuter(packed=packed):
            return False

        if not self.parseInner():
            return False

        return True

    def parseOuter(self, packed=None):
        '''
        Parses raw packet head from packed if provided or .packed otherwise
        Deserializes head
        Unpacks rest of packet.
        Parses foot (signature) if given and verifies signature
        Returns False if not verified Otherwise True
        Result is .data
        '''
        self.error = ''
        if packed:
            self.packed = packed
        if not self.packed:
            self.error = "Packed empty, nothing to parse."
            return False

        if not self.head.parse():
            return False
        if self.data['vn'] not in raeting.VERSIONS.values():
            self.error = ("Received incompatible version '{0}'"
            "version '{1}'".format(self.data['vn']))
            return False

        if not self.unpack():
            return False

        if not self.foot.parse():
            return False

        if not self.verify():
            return False

        return True

    def parseInner(self):
        '''
        Assumes the head as already been parsed so self.data is valid
        Assumes packet as already been unpacked
        Assumes foot signature has already been verified if any
        Parses coat if given and decrypts enclosed body
        Parses decrypted body and deserializes
        Returns True if decrypted deserialize successful Otherwise False
        Result is .body.data and .data
        '''
        self.error = ''
        if not self.coat.parse():
            return False
        if not self.decrypt():
            return False
        if not self.body.parse():
            return False
        return True

    def verify(self):
        '''
        Uses signature in foot to verify (authenticate) packet signature
        '''
        return True

    def decrypt(self):
        '''
        Uses coat to decrypt body
        '''
        return True
