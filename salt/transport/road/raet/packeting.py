# -*- coding: utf-8 -*-
'''
packeting module provides classes for Raet packets


'''

# Import python libs
import socket
from collections import Mapping
try:
    import simplejson as json
except ImportError:
    import json

# Import ioflo libs
from ioflo.base.odicting import odict
from ioflo.base.aiding import packByte, unpackByte

from . import raeting


class Stack(object):
    ''' RAET protocol stack object'''
    def __init__(self):
        ''' Setup Stack instance'''
        self.devices = odict()  # devices managed by this stack


class Device(object):
    ''' RAET protocol endpoint device object'''
    def __init__(self, did=0, stack=None, host='', port=raeting.RAET_PORT):
        ''' Setup Device instance'''
        self.did = did  # device id
        self.stack = stack  # Stack object that manages this device
        self.host = socket.gethostbyname(host)
        self.port = port

    @property
    def ha(self):
        '''ha property that returns ip address (host, port) tuple'''
        return (self.host, self.port)


class Part(object):
    '''
    Base class for parts of a RAET packet
    Should be subclassed
    '''
    def __init__(self, packet=None, kind=None, length=None, **kwa):
        ''' Setup Part instance '''
        self.packet = packet  # Packet this Part belongs too
        self.kind = kind   # part kind
        self.length = length  # specified length of part not computed length
        self.packed = ''

    def __len__(self):
        ''' Return the size property '''
        return self.size

    @property
    def size(self):
        ''' size property returns the length of the .packed of this Part'''
        return len(self.packed)


class Head(Part):
    '''
    RAET protocol packet header object
    Manages the header portion of a packet
    '''
    def __init__(self, **kwa):
        ''' Setup Head instance'''
        super(Head, self).__init__(**kwa)
        self.data = odict(raeting.HEAD_DEFAULTS)  # ensures correct order

    def pack(self):
        ''' Composes and returns .packed, which is the packed form of this part '''
        self.packed = ''
        self.data = odict(raeting.HEAD_DEFAULTS)  # refresh
        self.data['vn'] = self.packet.version
        self.data['pk'] = self.packet.kind

        self.data['cf'] = self.packet.crdrFlag
        self.data['mf'] = self.packet.multFlag
        self.data['bf'] = self.packet.brstFlag
        self.data['pf'] = self.packet.pendFlag
        self.data['af'] = self.packet.allFlag

        self.data['nk'] = self.packet.neck.kind
        self.data['nl'] = self.packet.neck.size
        self.data['bk'] = self.packet.body.kind
        self.data['bl'] = self.packet.body.size
        self.data['tk'] = self.packet.tail.kind
        self.data['tl'] = self.packet.tail.size

        self.data['fg'] = "{:02x}".format(self.packFlags())

        # kit always includes header kind and length fields
        kit = odict([('hk', self.kind), ('hl', 0)])
        for k, v in raeting.HEAD_DEFAULTS.items():  # include if not equal to default
            if (self.data[k] != v) and (k not in raeting.PACKET_FLAGS):
                kit[k] = self.data[k]

        if self.kind == raeting.headKinds.json:
            kit['hl'] = '00'  # need hex string so fixed length and jsonable
            packed = json.dumps(kit, separators=(',', ':'), encoding='ascii',)
            packed = '{0}{1}'.format(packed, raeting.JSON_END)
            self.length = len(packed)
            if self.length > raeting.MAX_HEAD_LEN:
                self.packet.error = "Head length of {0}, exceeds max of {1}".format(hl, MAX_HEAD_LEN)
                return self.packed
            # subsitute true length converted to 2 byte hex string
            self.packed = packed.replace('"hl":"00"', '"hl":"{0}"'.format("{0:02x}".format(self.length)[-2:]), 1)

        return self.packed

    def parse(self, rest):
        '''
        Parses and removes head from packed rest and returns remainder
        '''
        self.packed = ''
        self.data = odict(raeting.HEAD_DEFAULTS)  # refresh
        if rest.startswith('{"hk":1,') and raeting.JSON_END in rest:  # json header
            self.kind = raeting.headKinds.json
            front, sep, back = rest.partition(raeting.JSON_END)
            rest = back
            self.packed = "{0}{1}".format(front, sep)
            kit = json.loads(front,
                             encoding='ascii',
                             object_pairs_hook=odict)
            self.data.update(kit)
            if 'fg' in self.data:
                self.unpackFlags(self.data['fg'])

            if self.data['hk'] != self.kind:
                self.packet.error = 'Recognized head kind does not match head field value.'
                return rest

            self.length = int(self.data['hl'], 16)
            if self.length != self.size:
                self.packet.error = 'Actual head length does not match head field value.'

        else:  # notify unrecognizible packet head
            self.kind = raeting.headKinds.unknown
            self.packet.error = "Unrecognizible packet head."

        return rest

    def packFlags(self):
        ''' Packs all the flag fields into a single two char hex string '''
        values = []
        for field in raeting.PACKET_FLAG_FIELDS:
            values.append(1 if self.data.get(field, 0) else 0)
        return packByte(format='11111111', fields=values)

    def unpackFlags(self, flags):
        ''' Unpacks all the flag fields from a single two char hex string '''
        values = unpackByte(format='11111111', byte=int(flags, 16), boolean=False)
        for i, field in enumerate(raeting.PACKET_FLAG_FIELDS):
            if field in self.data:
                self.data[field] = values[i]


class Neck(Part):
    '''
    RAET protocol packet neck object
    Manages the signing or authentication of the packet
    '''
    def __init__(self, **kwa):
        ''' Setup Neck instance'''
        super(Neck, self).__init__(**kwa)

    def pack(self):
        ''' Composes and returns .packed, which is the packed form of this part '''
        self.packed = ''
        if self.kind == raeting.neckKinds.nada:
            pass
        return self.packed

    def parse(self, rest):
        ''' Parses and removes neck from rest and returns rest '''
        self.packed = ''
        self.kind = self.packet.head.data['nk']

        if self.kind not in raeting.NECK_KIND_NAMES:
            self.kind = raeting.neckKinds.unknown
            self.packet.error = "Unrecognizible packet neck."
            return rest

        self.length = self.packet.head.data['nl']
        self.packed = rest[:self.length]
        rest = rest[self.length:]

        if self.kind == raeting.neckKinds.nada:
            pass
        return rest


class Body(Part):
    '''
    RAET protocol packet body object
    Manages the messsage  portion of the packet
    '''
    def __init__(self, data=None, **kwa):
        ''' Setup Body instance'''
        super(Body, self).__init__(**kwa)
        self.data = data or odict()

    def pack(self):
        ''' Composes and returns .packed, which is the packed form of this part'''
        self.packed = ''
        if self.kind == raeting.bodyKinds.json:
            self.packed = json.dumps(self.data, separators=(',', ':'))
        return self.packed

    def parse(self, rest):
        ''' Parses and removes head from rest and returns rest '''
        self.packed = ''
        self.kind = self.packet.head.data['bk']

        if self.kind not in raeting.BODY_KIND_NAMES:
            self.kind = raeting.bodyKinds.unknown
            self.packet.error = "Unrecognizible packet body."
            return rest

        self.length = self.packet.head.data['bl']
        self.packed = rest[:self.length]
        rest = rest[self.length:]
        self.data = odict()

        if self.kind == raeting.bodyKinds.json:
            if self.length:
                kit = json.loads(self.packed, object_pairs_hook=odict)
                if not isinstance(kit, Mapping):
                    self.packet.error = "Packet body not a mapping."
                    return rest
                self.data = kit

        elif self.kind == raeting.bodyKinds.nada:
            pass

        return rest


class Tail(Part):
    '''
    RAET protocol packet tail object
    Manages the verification of the body portion of the packet
    '''
    def __init__(self, **kwa):
        ''' Setup Tail instal'''
        super(Tail, self).__init__(**kwa)

    def pack(self):
        '''
        Composes and returns .packed, which is the packed form of this part
        '''
        self.packed = ''
        if self.kind == raeting.tailKinds.nada:
            pass
        return self.packed

    def parse(self, rest):
        ''' Parses and removes tail from rest and returns rest '''
        self.packed = ''
        self.kind = self.packet.head.data['tk']

        if self.kind not in raeting.TAIL_KIND_NAMES:
            self.kind = raeting.tailKinds.unknown
            self.packet.error = "Unrecognizible packet tail."
            return rest

        self.length = self.packet.head.data['tl']
        self.packed = rest[:self.length]
        rest = rest[self.length:]

        if self.kind == raeting.tailKinds.nada:
            pass

        return rest


class Packet(object):
    ''' RAET protocol packet object '''
    def __init__(self, stack=None, version=None, kind=None,
                     sh='', sp=raeting.RAET_PORT,
                     dh='127.0.0.1', dp=raeting.RAET_PORT,
                     body=None, data=None, raw=None):
        ''' Setup Packet instance. Meta data for a packet. '''
        self.stack = stack  # stack that handles this packet
        self.version = version or raeting.HEAD_DEFAULTS['vn']
        self.kind = kind or raeting.HEAD_DEFAULTS['pk']
        self.src = Device(host=sh, port=sp)  # source device
        self.dst = Device(host=dh, port=dp)  # destination device
        self.head = Head(packet=self)
        self.neck = Neck(packet=self)
        self.body = Body(packet=self, data=body)
        self.tail = Tail(packet=self)
        self.packed = ''  # packed string
        self.error = ''
        if data:
            self.load(data)
        if raw:
            self.parse(raw)

    @property
    def size(self):
        ''' size property returns the length of the .packed of this Packet'''
        return len(self.packed)

    def load(self, data=None):
        ''' Loud up attributes of parts if provided '''
        data = data or odict()
        raeting.updateMissing(data, raeting.PACKET_DEFAULTS)
        self.version = data['vn']
        self.crdrFlag = data['cf']
        self.multFlag = data['mf']
        self.brstFlag = data['bf']
        self.pendFlag = data['pf']
        self.allFlag = data['af']

        self.src.did = data['sd']
        self.src.host = data['sh']
        self.src.port = data['sp']
        self.dst.did = data['dd']
        self.dst.host = data['dh']
        self.dst.port = data['dp']
        self.head.kind = data['hk']
        self.neck.kind = data['nk']
        self.body.kind = data['bk']
        self.tail.kind = data['tk']

    def pack(self):
        ''' pack the parts of the packet and then the full packet'''
        self.error = ''
        self.body.pack()
        self.tail.pack()
        self.head.pack()
        self.neck.pack()
        self.packed = '{0}{1}{2}{3}'.format(self.head.packed, self.neck.packed, self.body.packed, self.tail.packed)
        return self.packed

    def parse(self, raw):
        ''' Parses raw packet '''
        self.error = ''
        rest = self.head.parse(raw)
        rest = self.neck.parse(rest)
        if not self.vouch():
            return
        rest = self.body.parse(rest)
        rest = self.tail.parse(rest)
        if not self.verify():
            return

        return rest

    def vouch(self):
        ''' Uses signature in neck to vouch for (authenticate) packet '''

        return True

    def verify(self):
        ''' Uses tail to verify body does not have errors '''

        return True
