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

try:
    import msgpack
except ImportError:
    mspack = None

# Import ioflo libs
from ioflo.base.odicting import odict
from ioflo.base.aiding import packByte, unpackByte

from ioflo.base.consoling import getConsole
console = getConsole()

from . import raeting

class Part(object):
    '''
    Base class for parts of a RAET packet
    Should be subclassed
    '''

    def __init__(self, packet=None, **kwa):
        '''
        Setup Part instance
        '''
        self.packet = packet  # Packet this Part belongs too
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
    RAET protocol transmit packet header class
    '''
    def pack(self):
        '''
        Composes .packed, which is the packed form of this part
        '''
        self.packed = ''
        data = self.packet.data  # for speed
        data['fl'] = self.packet.foot.size
        data['fg'] = "{:02x}".format(self.packFlags())

        # kit always includes raet id, packet length, and header kind fields
        kit = odict([('ri', 'RAET'), ('pl', 0), ('hl', 0)])
        for k, v in raeting.PACKET_DEFAULTS.items():  # include if not equal to default
            if ((k in raeting.HEAD_FIELDS) and
                (k not in raeting.PACKET_FLAGS) and
                (data[k] != v)):
                kit[k] = data[k]

        if data['hk'] == raeting.headKinds.raet:
            packed = ''
            lines = []
            for k, v in kit.items():
                lines.append("{key} {val:{fmt}}".format(
                        key=k, val=v, fmt=raeting.FIELD_FORMATS[k]))

            packed = "\n".join(lines)
            packed = '{0}{1}'.format(packed, raeting.HEAD_END)
            hl = len(packed)
            if hl > raeting.MAX_HEAD_SIZE:
                emsg = "Head length of {0}, exceeds max of {1}".format(hl, MAX_HEAD_SIZE)
                raise raeting.PacketError(emsg)
            data['hl'] = hl

            if self.packet.coat.size > raeting.MAX_MESSAGE_SIZE:
                emsg = "Packed message length of {0}, exceeds max of {1}".format(
                         self.packet.coat.size, raeting.MAX_MESSAGE_SIZE)
                raise raeting.PacketError(emsg)
            pl = hl + self.packet.coat.size + data['fl']
            data['pl'] = pl
            # Tray checks for packet length greater than UDP_MAX_PACKET_SIZE
            # and segments appropriately so pl may be truncated below in this case
            # substitute true lengths
            packed = packed.replace('\npl {val:{fmt}}\n'.format(
                                        val=kit['pl'],
                                        fmt=raeting.FIELD_FORMATS['pl']),
                                    '\npl {0}\n'.format("{val:{fmt}}".format(
                                        val=pl,
                                        fmt=raeting.FIELD_FORMATS['pl'])[-4:]),
                                    1)
            packed = packed.replace('\nhl {val:{fmt}}\n'.format(
                                        val=kit['hl'],
                                        fmt=raeting.FIELD_FORMATS['hl']),
                                    '\nhl {0}\n'.format("{val:{fmt}}".format(
                                            val=hl,
                                            fmt=raeting.FIELD_FORMATS['hl'])[-2:]),
                                    1)
            self.packed = packed

        elif data['hk'] == raeting.headKinds.json:
            kit['pl'] = '0000000'  # need hex string so fixed length and jsonable
            kit['hl'] = '00'  # need hex string so fixed length and jsonable
            packed = json.dumps(kit, separators=(',', ':'), encoding='ascii',)
            packed = '{0}{1}'.format(packed, raeting.JSON_END)
            hl = len(packed)
            if hl > raeting.MAX_HEAD_SIZE:
                emsg = "Head length of {0}, exceeds max of {1}".format(hl, MAX_HEAD_SIZE)
                raise raeting.PacketError(emsg)
            data['hl'] = hl

            if self.packet.coat.size > raeting.MAX_MESSAGE_SIZE:
                emsg = "Packed message length of {0}, exceeds max of {1}".format(
                         self.packet.coat.size, raeting.MAX_MESSAGE_SIZE)
                raise raeting.PacketError(emsg)
            pl = hl + self.packet.coat.size + data['fl']
            data['pl'] = pl
            #substitute true length converted to 2 byte hex string
            packed = packed.replace('"pl":"0000000"', '"pl":"{0}"'.format("{0:07x}".format(pl)[-7:]), 1)
            self.packed = packed.replace('"hl":"00"', '"hl":"{0}"'.format("{0:02x}".format(hl)[-2:]), 1)



    def packFlags(self):
        '''
        Packs all the flag fields into a single two char hex string
        '''
        values = []
        for field in raeting.PACKET_FLAG_FIELDS:
            values.append(1 if self.packet.data.get(field, 0) else 0)
        return packByte(fmt='11111111', fields=values)

class RxHead(Head):
    '''
    RAET protocol receive packet header class
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

        if packed.startswith('ri RAET\n') and raeting.HEAD_END in packed: # raet head
            hk = raeting.headKinds.raet
            front, sep, back = packed.partition(raeting.HEAD_END)
            self.packed = "{0}{1}".format(front, sep)
            kit = odict()
            lines = front.split('\n')
            for line in lines:
                key, val = line.split(' ')
                if key not in raeting.HEAD_FIELDS:
                    emsg = "Unknown head field '{0}'".format(key)
                    raise raeting.PacketError(emsg)
                if 'x' in raeting.FIELD_FORMATS[key]:
                    val = int(val, 16)
                elif 'd' in raeting.FIELD_FORMATS[key]:
                    val = int(val)
                elif 'f' in raeting.FIELD_FORMATS[key]:
                    val = float(val)
                kit[key] = val

            data.update(kit)
            if 'fg' in data:
                self.unpackFlags(data['fg'])

            if data['hk'] != hk:
                emsg = 'Recognized head kind does not match head field value.'
                raise raeting.PacketError(emsg)

            if data['hl'] != self.size:
                emsg = 'Actual head length = {0} not match head field = {1}'.format(
                        self.size, data['hl'])
                raise raeting.PacketError(emsg)

            if data['pl'] != self.packet.size:
                emsg = 'Actual packet length = {0} not match head field = {1}'.format(
                    self.packet.size, data['pl'])
                raise raeting.PacketError(emsg)


        elif packed.startswith('{"ri":"RAET",') and raeting.JSON_END in packed: # json head
            hk = raeting.headKinds.json
            front, sep, back = packed.partition(raeting.JSON_END)
            self.packed = "{0}{1}".format(front, sep)
            kit = json.loads(front,
                             encoding='ascii',
                             object_pairs_hook=odict)
            data.update(kit)
            if 'fg' in data:
                self.unpackFlags(data['fg'])

            if data['hk'] != hk:
                emsg = 'Recognized head kind does not match head field value.'
                raise raeting.PacketError(emsg)

            hl = int(data['hl'], 16)
            if hl != self.size:
                emsg = 'Actual head length does not match head field value.'
                raise raeting.PacketError(emsg)
            data['hl'] = hl
            pl = int(data['pl'], 16)
            if pl != self.packet.size:
                emsg = 'Actual packet length does not match head field value.'
                raise raeting.PacketError(emsg)
            data['pl'] = pl

        else:  # notify unrecognizable packet head
            data['hk'] = raeting.headKinds.unknown
            emsg = "Unrecognizable packet head."
            raise raeting.PacketError(emsg)

    def unpackFlags(self, flags):
        '''
        Unpacks all the flag fields from a single two char hex string
        '''
        values = unpackByte(fmt='11111111', byte=int(flags, 16), boolean=True)
        for i, field in enumerate(raeting.PACKET_FLAG_FIELDS):
            if field in self.packet.data:
                self.packet.data[field] = values[i]

class Body(Part):
    '''
    RAET protocol packet body class
    Manages the message portion of the packet
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
        bk = self.packet.data['bk']
        if bk == raeting.bodyKinds.json:
            if self.data:
                self.packed = json.dumps(self.data, separators=(',', ':'))
        elif bk == raeting.bodyKinds.msgpack:
            if self.data:
                if not msgpack:
                    emsg = "Msgpack not installed."
                    raise raeting.PacketError(emsg)
                self.packed = msgpack.dumps(self.data)
        elif bk == raeting.bodyKinds.raw:
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
        bk = self.packet.data['bk']

        if bk not in raeting.BODY_KIND_NAMES:
            self.packet.data['bk']= raeting.bodyKinds.unknown
            emsg = "Unrecognizable packet body."
            raise raeting.PacketError(emsg)

        self.data = odict()

        if bk == raeting.bodyKinds.json:
            if self.packed:
                kit = json.loads(self.packed, object_pairs_hook=odict)
                if not isinstance(kit, Mapping):
                    emsg = "Packet body not a mapping."
                    raise raeting.PacketError(emsg)
                self.data = kit
        elif bk == raeting.bodyKinds.msgpack:
            if self.packed:
                if not msgpack:
                    emsg = "Msgpack not installed."
                    raise raeting.PacketError(emsg)
                kit = msgpack.loads(self.packed, object_pairs_hook=odict)
                if not isinstance(kit, Mapping):
                    emsg = "Packet body not a mapping."
                    raise raeting.PacketError(emsg)
                self.data = kit
        elif bk == raeting.bodyKinds.raw:
            self.data = self.packed # return as string
        elif bk == raeting.bodyKinds.nada:
            pass

class Coat(Part):
    '''
    RAET protocol packet coat class
    Supports encapsulated encrypt/decrypt of body portion of packet
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
        ck = self.packet.data['ck']

        if ck == raeting.coatKinds.nacl:
            msg = self.packet.body.packed
            if msg:
                cipher, nonce = self.packet.encrypt(msg)
                self.packed = "".join([cipher, nonce])

        if ck == raeting.coatKinds.nada:
            self.packed = self.packet.body.packed

class RxCoat(Coat):
    '''
    RAET protocol rx packet coat class
    '''
    def parse(self):
        '''
        Parses coat. Assumes already unpacked.
        '''
        ck = self.packet.data['ck']

        if ck not in raeting.COAT_KIND_NAMES:
            self.packet.data['ck'] = raeting.coatKinds.unknown
            emsg = "Unrecognizable packet coat."
            raise raeting.PacketError(emsg)

        if ck == raeting.coatKinds.nacl:
            if self.packed:
                tl = raeting.tailSizes.nacl # nonce length
                cipher = self.packed[:-tl]
                nonce = self.packed[-tl:]
                msg = self.packet.decrypt(cipher, nonce)
                self.packet.body.packed = msg
            else:
                self.packet.body.packed = self.packed

        if ck == raeting.coatKinds.nada:
            self.packet.body.packed = self.packed
            pass

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
        fk = self.packet.data['fk']

        if fk not in raeting.FOOT_KIND_NAMES:
            self.packet.data['fk'] = raeting.footKinds.unknown
            emsg = "Unrecognizable packet foot."
            raise raeting.PacketError(emsg)

        if fk == raeting.footKinds.nacl:
            self.packed = "".rjust(raeting.footSizes.nacl, '\x00')

        elif fk == raeting.footKinds.nada:
            pass

    def sign(self):
        '''
        Compute signature on packet.packed and update packet.packet with signature
        '''
        fk = self.packet.data['fk']
        if fk not in raeting.FOOT_KIND_NAMES:
            self.packet.data['fk'] = raeting.footKinds.unknown
            emsg = "Unrecognizable packet foot."
            raise raeting.PacketError(emsg)

        if fk == raeting.footKinds.nacl:
            self.packed = self.packet.signature(self.packet.packed)

        elif fk == raeting.footKinds.nada:
            pass

class RxFoot(Foot):
    '''
    RAET protocol receive packet foot class
    '''
    def parse(self):
        '''
        Parses foot. Assumes foot already unpacked
        '''
        fk = self.packet.data['fk']
        fl = self.packet.data['fl']
        self.packed = ''

        if fk not in raeting.FOOT_KIND_NAMES:
            self.packet.data['fk'] = raeting.footKinds.unknown
            emsg = "Unrecognizable packet foot."
            raise raeting.PacketError(emsg)

        if self.packet.size < fl:
            emsg = "Packet size not big enough for foot."
            raise raeting.PacketError(emsg)

        self.packed = self.packet.packed[self.packet.size - fl:]

        if fk == raeting.footKinds.nacl:
            if self.size != raeting.footSizes.nacl:
                emsg = ("Actual foot size '{0}' does not match "
                    "kind size '{1}'".format(self.size, raeting.footSizes.nacl))
                raise raeting.PacketError(emsg)

            signature = self.packed
            blank = "".rjust(raeting.footSizes.nacl, '\x00')

            front = self.packet.packed[:self.packet.size - fl]

            msg = "".join([front, blank])
            if not self.packet.verify(signature, msg):
                emsg = "Failed verification"
                raise raeting.PacketError(emsg)

        if fk == raeting.footKinds.nada:
            pass

class Packet(object):
    '''
    RAET protocol packet object
    '''
    def __init__(self, stack=None, data=None, kind=None):
        ''' Setup Packet instance. Meta data for a packet. '''
        self.stack = stack
        self.packed = ''  # packed string
        self.data = odict(raeting.PACKET_DEFAULTS)
        if data:
            self.data.update(data)
        if kind:
            if kind not in raeting.PCKT_KIND_NAMES:
                self.data['pk'] = raeting.pcktKinds.unknown
                emsg = "Unrecognizable packet kind."
                raise raeting.PacketError(emsg)
            self.data.update(pk=kind)

    @property
    def size(self):
        '''
        Property is the length of the .packed of this Packet
        '''
        return len(self.packed)

    @property
    def segmentive(self):
        '''
        Property is True
        If packet segment flag is True Or packet segment count is > 1
        '''
        return (True if (self.data.get('sf') or (self.data.get('sc', 1) > 1)) else False)

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
    def __init__(self, embody=None, **kwa):
        '''
        Setup TxPacket instance
        '''
        super(TxPacket, self).__init__(**kwa)
        self.head = TxHead(packet=self)
        self.body = TxBody(packet=self, data=embody)
        self.coat = TxCoat(packet=self)
        self.foot = TxFoot(packet=self)

    @property
    def index(self):
        '''
        Property is transaction tuple (rf, le, re, si, ti, bf,)
        '''
        data = self.data
        le = data['se']
        if le == 0:
            le = (data['sh'], data['sp'])
        re = data['de']
        if re == 0:
            re = (data['dh'], data['dp'])
        return ((data['cf'], le, re, data['si'], data['ti'], data['bf']))

    def signature(self, msg):
        '''
        Return signature resulting from signing msg
        '''
        return (self.stack.estate.signer.signature(msg))

    def sign(self):
        '''
        Sign packet with foot
        '''
        self.foot.sign()
        self.packed = ''.join([self.head.packed,
                               self.coat.packed,
                               self.foot.packed])

    def encrypt(self, msg):
        '''
        Return (cipher, nonce) duple resulting from encrypting message
        with short term keys
        '''
        remote = self.stack.estates[self.data['de']]
        return (remote.privee.encrypt(msg, remote.publee.key))

    def prepack(self):
        '''
        Pre Pack the parts of the packet .packed but do not sign so can see
        if needs to be segmented
        '''
        self.body.pack()
        self.coat.pack()
        self.foot.pack()
        self.head.pack()
        self.packed = ''.join([self.head.packed,
                               self.coat.packed,
                               self.foot.packed])


    def pack(self):
        '''
        Pack the parts of the packet and then the full packet into .packed
        '''
        self.prepack()
        if self.size > raeting.UDP_MAX_PACKET_SIZE:
            emsg = "Packet length of {0}, exceeds max of {1}".format(
                    self.size, raeting.UDP_MAX_PACKET_SIZE)
            raise raeting.PacketError(emsg)

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
        Property is transaction tuple (rf, le, re, si, ti, bf,)
        '''
        data = self.data
        le = data['de']
        if le == 0:
            le = (data['dh'], data['dp'])
        re = data['se']
        if re == 0:
            re = (data['sh'], data['sp'])
        return ((not data['cf'], le, re, data['si'], data['ti'], data['bf']))

    def verify(self, signature, msg):
        '''
        Return result of verifying msg with signature
        '''
        return (self.stack.estates[self.data['se']].verfer.verify(signature, msg))

    def decrypt(self, cipher, nonce):
        '''
        Return msg resulting from decrypting cipher and nonce
        with short term keys
        '''
        remote = self.stack.estates[self.data['se']]
        return (remote.privee.decrypt(cipher, nonce, remote.publee.key))

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

        self.foot.parse() #foot unpacks itself

    def unpackInner(self, packed=None):
        '''
        Unpacks the body, and coat parts of .packed
        Assumes that the lengths of the parts are valid in .data as would be
        the case after successfully parsing the head section
        '''
        hl = self.data['hl']
        fl = self.data['fl']
        self.coat.packed = self.packed[hl:self.size - fl] #coat.parse loads body.packed

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
        self.unpackInner()
        self.coat.parse()
        self.body.parse()

class Tray(object):
    '''
    Manages messages, segmentation when needed and the associated packets
    '''
    def __init__(self, stack=None, data=None, body=None, packed=None,  **kwa):
        '''
        Setup instance
        '''
        self.stack = stack
        self.packed = packed or ''
        self.data = odict(raeting.PACKET_DEFAULTS)
        if data:
            self.data.update(data)
        self.body = body #body data of message

    @property
    def size(self):
        '''
        Property is the length of the .packed
        '''
        return len(self.packed)

class TxTray(Tray):
    '''
    Manages an outgoing message and ites associated packet(s)
    '''
    def __init__(self, **kwa):
        '''
        Setup instance
        '''
        super(TxTray, self).__init__(**kwa)
        self.packets = []
        self.current = 0 # next  packet to send
        self.last = 0 # last packet sent

    def pack(self, data=None, body=None):
        '''
        Convert message in .body into one or more packets
        '''
        if data:
            self.data.update(data)
        if body is not None:
            self.body = body

        self.current = 0
        self.packets = []
        packet = TxPacket(stack=self.stack,
                          kind=raeting.pcktKinds.message,
                          embody=self.body,
                          data=self.data)

        packet.prepack()
        if packet.size <= raeting.UDP_MAX_PACKET_SIZE:
            packet.sign()
            self.packets.append(packet)
        else:
            self.packed = packet.coat.packed
            self.packetize(headsize=packet.head.size, footsize=packet.foot.size)

    def packetize(self, headsize, footsize):
        '''
        Create packeted segments from .packed using headsize footsize
        '''
        extrasize = 0
        if self.data['hk'] == raeting.headKinds.raet:
            extrasize = 27 # extra header size as a result of segmentation
        elif self.data['hk'] == raeting.headKinds.json:
            extrasize = 36 # extra header size as a result of segmentation

        hotelsize = headsize + extrasize + footsize
        segsize = raeting.UDP_MAX_PACKET_SIZE - hotelsize

        segcount = (self.size // segsize) + (1 if self.size % segsize else 0)
        for i in range(segcount):
            if i == segcount - 1: #last segment
                segment = self.packed[i * segsize:]
            else:
                segment = self.packed[i * segsize: (i+1) * segsize]

            packet = TxPacket( stack=self.stack,
                                data=self.data)
            packet.data.update(sn=i, sc=segcount, ml=self.size, sf=True)
            packet.coat.packed = packet.body.packed = segment
            packet.foot.pack()
            packet.head.pack()
            packet.packed = ''.join([  packet.head.packed,
                                        packet.coat.packed,
                                        packet.foot.packed])
            packet.sign()
            self.packets.append(packet)


class RxTray(Tray):
    '''
    Manages segmentated messages and the associated packets
    '''
    def __init__(self, segments=None, **kwa):
        '''
        Setup instance
        '''
        super(RxTray, self).__init__(**kwa)
        self.segments = segments if segments is not None else []
        self.complete = False
        self.last = 0 # last packet number received
        self.prev = 0 # previous packet number received

    def parse(self, packet):
        '''
        Process a given packet assumes parseOuter done already
        '''
        sc = packet.data['sc']
        self.prev = self.last
        self.last = sn = packet.data['sn']
        console.verbose("segment count={0} number={1} tid={2}\n".format(
            sc, sn, packet.data['ti']))

        if sc == 1:
            self.data.update(packet.data)
            packet.parseInner()
            self.body = packet.body.data
            self.complete = True
            return self.body

        if not self.segments: #get data from first packet received
            self.data.update(packet.data)
            self.segments = [None] * sc

        hl = packet.data['hl']
        fl = packet.data['fl']
        segment = packet.packed[hl:packet.size - fl]

        self.segments[sn] = segment
        if None in self.segments: #don't have all segments yet
            return None
        self.body = self.desegmentize()
        return self.body

    def missing(self, begin=None, end=None):
        '''
        return list of missing packet numbers between begin and end
        '''
        if begin is None:
            begin = 0
        if end is None:
            end = len(self.segments)
        if begin >= end:
            return []
        misseds = []
        for i, segment in enumerate(self.segments[begin:end]):
            if segment is None:
                misseds.append(i)
        return misseds

    def desegmentize(self):
        '''
        Process message packet assumes already parsed outer so verified signature
        and processed header data
        '''
        sc = self.data['sc']
        self.packed = "".join(self.segments)
        ml = self.data['ml']
        if sc > 1 and self.size != ml:
            emsg = ("Full message payload length '{0}' does not equal head field"
                                          " '{1}'".format(self.size, ml))
            raise raeting.PacketError(emsg)

        packet = RxPacket(stack = self.stack, data=self.data)
        packet.coat.packed = self.packed

        packet.coat.parse()
        packet.body.parse()
        self.complete = True

        return packet.body.data


