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
        data['nk'] = self.packet.neck.kind
        data['nl'] = self.packet.neck.size
        data['bk'] = self.packet.body.kind
        data['bl'] = self.packet.body.size
        data['tk'] = self.packet.tail.kind
        data['tl'] = self.packet.tail.size

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
        values = unpackByte(format='11111111', byte=int(flags, 16), boolean=False)
        for i, field in enumerate(raeting.PACKET_FLAG_FIELDS):
            if field in self.packet.data:
                self.packet.data[field] = values[i]


class Neck(Part):
    '''
    RAET protocol packet neck class
    Manages the signing or authentication of the packet
    '''
    def __init__(self, **kwa):
        '''
        Setup Neck instance
        '''
        super(Neck, self).__init__(**kwa)


class TxNeck(Neck):
    '''
    RAET protocol transmit packet neck class
    '''

    def pack(self):
        '''
        Composes and returns .packed, which is the packed form of this part
        '''
        self.packed = ''
        self.kind = self.packet.data['nk']

        if self.kind not in raeting.NECK_KIND_NAMES:
            self.kind = raeting.neckKinds.unknown
            self.packet.error = "Unrecognizible packet neck."
            return self.packed

        if self.kind == raeting.neckKinds.nacl:
            self.packed = "".rjust(raeting.neckSizes.nacl, '\x00')

        elif self.kind == raeting.neckKinds.nada:
            pass

        return self.packed


class RxNeck(Neck):
    '''
    RAET protocol receive packet neck class
    '''
    def parse(self):
        '''
        Parses neck. Assumes neck already unpacked
        '''
        self.kind = self.packet.data['nk']

        if self.kind not in raeting.NECK_KIND_NAMES:
            self.kind = raeting.neckKinds.unknown
            self.packet.error = "Unrecognizible packet neck."
            return False

        if self.kind == raeting.neckKinds.nacl:
            if self.size != raeting.neckSizes.nacl:
                self.packet.error = ("Actual neck size '{0}' does not match "
                    "kind size '{1}'".format(self.size, raeting.neckSizes.nacl))
                return False

        if self.kind == raeting.neckKinds.nada:
            pass

        return True


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


class Tail(Part):
    '''
    RAET protocol packet tail class
    Supports encrypt/decrypt or other validation of body portion of packet
    '''
    def __init__(self, **kwa):
        ''' Setup Tail instal'''
        super(Tail, self).__init__(**kwa)


class TxTail(Tail):
    '''
    RAET protocol tx packet tail class
    '''

    def pack(self):
        '''
        Composes and returns .packed, which is the packed form of this part
        '''
        self.packed = ''
        self.kind = self.packet.data['tk']

        if self.kind == raeting.tailKinds.nacl:
            self.packed = "".rjust(raeting.tailSizes.nacl, '\x00')

        if self.kind == raeting.tailKinds.nada:
            pass
        return self.packed


class RxTail(Tail):
    '''
    RAET protocol rx packet tail class
    '''

    def parse(self):
        '''
        Parses tail. Assumes already unpacked.
        '''
        self.kind = self.packet.data['tk']

        if self.kind not in raeting.TAIL_KIND_NAMES:
            self.kind = raeting.tailKinds.unknown
            self.packet.error = "Unrecognizible packet tail."
            return False

        if self.kind == raeting.tailKinds.nacl:
            if self.size != raeting.tailSizes.nacl:
                self.packet.error = ("Actual tail size '{0}' does not match "
                    "kind size '{1}'".format(self.size, raeting.tailSizes.nacl))
                return False

        if self.kind == raeting.tailKinds.nada:
            pass

        return True


class Packet(object):
    '''
    RAET protocol packet object
    '''
    def __init__(self, kind=None):
        ''' Setup Packet instance. Meta data for a packet. '''
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
        self.neck = TxNeck(packet=self)
        self.body = TxBody(packet=self, data=embody)
        self.tail = TxTail(packet=self)
        if data:
            self.data.update(data)

    def pack(self):
        '''
        Pack the parts of the packet and then the full packet
        '''
        self.error = ''
        self.body.pack()
        self.tail.pack()
        self.neck.pack()
        self.head.pack()
        self.packed = ''.join([self.head.packed, self.neck.packed, self.body.packed, self.tail.packed])
        self.sign()
        return self.packed

    def sign(self):
        '''
        Sign .packed using neck
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
        self.neck = RxNeck(packet=self)
        self.body = RxBody(packet=self)
        self.tail = RxTail(packet=self)
        self.packed = packed or ''

    def unpack(self, packed=None):
        '''
        Unpacks the neck, body, and tail parts of .packed
        Assumes that the lengths of the parts are valid in .data as would be
        the case after successfully parsing the head section
        '''
        hl = self.data['hl']
        nl = self.data['nl']
        bl = self.data['bl']
        tl = self.data['tl']
        if self.size != (hl + nl + bl + tl):
            self.error = ("Whole size {0} does not equal sum of the parts"
                          " '{1}'".format(self.size, hl + nl + bl + tl))
            return False

        self.neck.packed = self.packed[hl:hl+nl]
        self.body.packed = self.packed[hl+nl:hl+nl+bl]
        self.tail.packed = self.packed[hl+nl+bl:hl+nl+bl+tl]
        return True

    def parse(self, packed=None):
        '''
        Parses raw packet completely
        Result is .data and .body.data
        '''
        if not self.parseFore(packed=packed):
            return False

        if not self.parseBack():
            return False

        return True

    def parseFore(self, packed=None):
        '''
        Parses raw packet head and neck from packed if provided or .packed otherwise
        Returns True if verified Otherwise False
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

        if not self.unpack():
            return False

        if self.data['vn'] not in raeting.VERSIONS.values():
            self.error = ("Received incompatible version '{0}'"
            "version '{1}'".format(self.data['vn']))
            return False

        if not self.neck.parse():
            return False

        if not self.verify():
            return False

        return True

    def parseBack(self):
        '''
        Parses raw packet body and tail and validates
        Assumes the head and neck have already been parsed so self.data is valid
        Returns True if verified Otherwise False
        Result is .body.data and .data
        '''
        if not self.tail.parse():
            return False
        if not self.validate():
            return False
        if not self.body.parse():
            return False
        return True

    def verify(self):
        '''
        Uses signature in neck to verify (authenticate) packet signature
        '''
        return True

    def validate(self):
        '''
        Uses tail to validate body such as decrypt
        '''
        return True
