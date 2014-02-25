# -*- coding: utf-8 -*-
'''
stacking.py raet protocol stacking classes
'''
# pylint: skip-file
# pylint: disable=W0611

# Import python libs
import socket
import binascii
import struct

try:
    import simplejson as json
except ImportError:
    import json

# Import ioflo libs
from ioflo.base.odicting import odict
from ioflo.base import aiding

from . import raeting
from . import nacling
from . import packeting
from . import devicing

from ioflo.base.consoling import getConsole
console = getConsole()


class Transaction(object):
    '''
    RAET protocol transaction class
    '''
    Timeout =  5.0 # default timeout

    def __init__(self, stack=None, kind=None, timeout=None, start=None,
                 rdid=None, rmt=False, bcst=False, sid=None, tid=None,
                 txData=None, txPacket=None, rxPacket=None):
        '''
        Setup Transaction instance
        timeout of 0.0 means no timeout go forever
        '''
        self.stack = stack
        self.kind = kind or raeting.PACKET_DEFAULTS['tk']

        if timeout is None:
            timeout = self.Timeout
        self.timeout = timeout
        self.timer = aiding.StoreTimer(self.stack.store, duration=self.timeout)
        if start: #enables synchronized starts not just current time
            self.timer.restart(start=start)

        # local device is the .stack.device
        self.rdid = rdid  # remote device did

        self.rmt = rmt
        self.bcst = bcst

        self.sid = sid
        self.tid = tid

        self.txData = txData or odict() # data used to prepare last txPacket
        self.txPacket = txPacket  # last tx packet needed for retries
        self.rxPacket = rxPacket  # last rx packet

    @property
    def index(self):
        '''
        Property is transaction tuple (rf, ld, rd, si, ti, bf,)
        '''
        return ((self.rmt, self.stack.device.did, self.rdid, self.sid, self.tid, self.bcst,))

    def process(self):
        '''
        Process time based handling of transaction like timeout or retries
        '''
        pass

    def receive(self, packet):
        '''
        Process received packet
        '''
        self.rxPacket = packet

    def transmit(self, packet):
        '''
        Queue tx duple on stack transmit queue
        '''
        self.stack.txUdp(packet.packed, self.rdid)
        self.txPacket = packet

    def add(self, index=None):
        '''
        Add self to stack transactions
        '''
        if not index:
            index = self.index
        self.stack.addTransaction(index, self)

    def remove(self, index=None):
        '''
        Remove self from stack transactions
        '''
        if not index:
            index = self.index
        self.stack.removeTransaction(index, transaction=self)

class Initiator(Transaction):
    '''
    RAET protocol initiator transaction class
    '''
    def __init__(self, **kwa):
        '''
        Setup Transaction instance
        '''
        kwa['rmt'] = False  # force rmt to False
        super(Initiator, self).__init__(**kwa)

    def process(self):
        '''
        Process time based handling of transaction like timeout or retries
        '''
        if self.timeout > 0.0 and self.timer.expired:
            self.stack.removeTransaction(self.index, transaction=self)

class Correspondent(Transaction):
    '''
    RAET protocol correspondent transaction class
    '''
    Requireds = ['sid', 'tid', 'rxPacket']

    def __init__(self, **kwa):
        '''
        Setup Transaction instance
        '''
        kwa['rmt'] = True  # force rmt to True

        missing = []
        for arg in self.Requireds:
            if arg not in kwa:
                missing.append(arg)
        if missing:
            emsg = "Missing required keyword arguments: '{0}'".format(missing)
            raise TypeError(emsg)

        super(Correspondent, self).__init__(**kwa)

class Joiner(Initiator):
    '''
    RAET protocol Joiner Initiator class Dual of Joinent
    '''
    def __init__(self, mha = None, **kwa):
        '''
        Setup Transaction instance
        '''
        kwa['kind'] = raeting.trnsKinds.join
        super(Joiner, self).__init__(**kwa)

        if mha is None:
            mha = ('127.0.0.1', raeting.RAET_PORT)

        if self.rdid is None:
            if not self.stack.devices: # no channel master so make one
                master = devicing.RemoteDevice(did=0, ha=mha)
                self.stack.addRemoteDevice(master)

            self.rdid = self.stack.devices.values()[0].did # zeroth is channel master
        self.sid = 0
        self.tid = self.stack.devices[self.rdid].nextTid()
        self.prep()
        self.add(self.index)

    def receive(self, packet):
        """
        Process received packet belonging to this transaction
        """
        super(Joiner, self).receive(packet) #  self.rxPacket = packet

        if packet.data['tk'] == raeting.trnsKinds.join:
            if packet.data['pk'] == raeting.pcktKinds.ack: #pended
                self.pend()
            elif packet.data['pk'] == raeting.pcktKinds.response:
                self.accept()

    def prep(self):
        '''
        Prepare .txData
        '''
        self.txData.update( sh=self.stack.device.host,
                            sp=self.stack.device.port,
                            dh=self.stack.devices[self.rdid].host,
                            dp=self.stack.devices[self.rdid].port,
                            sd=self.stack.device.did,
                            dd=self.rdid,
                            tk=self.kind,
                            cf=self.rmt,
                            bf=self.bcst,
                            si=self.sid,
                            ti=self.tid,
                            ck=raeting.coatKinds.nada,
                            fk=raeting.footKinds.nada)

    def join(self):
        '''
        Send join request
        '''
        if self.rdid not in self.stack.devices:
            emsg = "Invalid remote destination device id '{0}'".format(self.rdid)
            raise raeting.TransactionError(emsg)

        body = odict([('name', self.stack.device.name),
                      ('verhex', self.stack.device.signer.verhex),
                      ('pubhex', self.stack.device.priver.pubhex)])
        packet = packeting.TxPacket(stack=self.stack,
                                    kind=raeting.pcktKinds.request,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except raeting.PacketError as ex:
            print ex
            self.remove()
            return
        self.transmit(packet)

    def pend(self):
        '''
        Process ack to join packet
        '''
        if not self.stack.parseInner(self.rxPacket):
            return
        #data = self.rxPacket.data
        #body = self.rxPacket.body.data
        #set timer for redo
        pass

    def accept(self):
        '''
        Perform acceptance in response to join response packt
        '''
        if not self.stack.parseInner(self.rxPacket):
            return
        data = self.rxPacket.data
        body = self.rxPacket.body.data

        ldid = body.get('ldid')
        if not ldid:
            emsg = "Missing local device id in accept packet"
            raise raeting.TransactionError(emsg)

        rdid = body.get('rdid')
        if not rdid:
            emsg = "Missing remote device id in accept packet"
            raise raeting.TransactionError(emsg)

        name = body.get('name')
        if not name:
            emsg = "Missing remote name in accept packet"
            raise raeting.TransactionError(emsg)

        verhex = body.get('verhex')
        if not verhex:
            emsg = "Missing remote verifier key in accept packet"
            raise raeting.TransactionError(emsg)

        pubhex = body.get('pubhex')
        if not pubhex:
            emsg = "Missing remote crypt key in accept packet"
            raise raeting.TransactionError(emsg)

        index = self.index # save before we change it

        self.stack.device.did = ldid
        remote = self.stack.devices[self.rdid]
        remote.verfer = nacling.Verifier(key=verhex)
        remote.pubber = nacling.Publican(key=pubhex)
        if remote.did != rdid: #move remote device to new index
            self.stack.moveRemoteDevice(old=remote.did, new=rdid)
        if remote.name != name: # rename remote device to new name
            self.stack.renameRemoteDevice(old=remote.name, new=name)
        remote.joined = True #accepted
        remote.nextSid()
        self.remove(index)

class Joinent(Correspondent):
    '''
    RAET protocol Joinent transaction class, dual of Joiner
    '''
    def __init__(self, **kwa):
        '''
        Setup Transaction instance
        '''
        kwa['kind'] = raeting.trnsKinds.join
        super(Joinent, self).__init__(**kwa)
        self.prep()
        # Since corresponding bootstrap transaction use packet.index not self.index
        self.add(self.rxPacket.index)

    def prep(self):
        '''
        Prepare .txData
        '''
        #since bootstrap transaction use the reversed sdid and ddid from packet
        self.txData.update( sh=self.stack.device.host,
                    sp=self.stack.device.port,
                    sd=self.rxPacket.data['dd'],
                    dd=self.rxPacket.data['sd'],
                    tk=self.kind,
                    cf=self.rmt,
                    bf=self.bcst,
                    si=self.sid,
                    ti=self.tid,
                    ck=raeting.coatKinds.nada,
                    fk=raeting.footKinds.nada,)

    def join(self):
        '''
        Process join packet
        Perform pend operation of pending remote device being accepted onto channel
        '''
        if not self.stack.parseInner(self.rxPacket):
            return
        data = self.rxPacket.data
        body = self.rxPacket.body.data

        name = body.get('name')
        if not name:
            emsg = "Missing remote name in join packet"
            raise raeting.TransactionError(emsg)

        verhex = body.get('verhex')
        if not verhex:
            emsg = "Missing remote verifier key in join packet"
            raise raeting.TransactionError(emsg)

        pubhex = body.get('pubhex')
        if not pubhex:
            emsg = "Missing remote crypt key in join packet"
            raise raeting.TransactionError(emsg)

        remote = self.stack.fetchRemoteDeviceByHostPort(host=data['sh'], port=data['sp'])
        if remote:
            if (name != remote.name or
                verhex != remote.verfer.keyhex or
                pubhex != remote.pubber.keyhex):
                # nack join request another device at same address but different credentials
                # and return
                pass
            # accept here and return

        if name in self.stack.dids:
            emsg = "Another device with name  already exists"
            raise raeting.TransactionError(emsg)



        remote = devicing.RemoteDevice( stack=self.stack,
                                        name=name,
                                        host=data['sh'],
                                        port=data['sp'],
                                        verkey=verhex,
                                        pubkey=pubhex,
                                        rsid=self.sid,
                                        rtid=self.tid, )
        self.stack.addRemoteDevice(remote) #provisionally add .accepted is None
        self.rdid = remote.did # auto generated at instance creation above

        self.ackJoin()

    def ackJoin(self):
        '''
        Send ack to join request
        '''
        if self.rdid not in self.stack.devices:
            emsg = "Invalid remote destination device id '{0}'".format(self.rdid)
            raise raeting.TransactionError(emsg)

        #since bootstrap transaction use updated self.rid
        self.txData.update( dh=self.stack.devices[self.rdid].host,
                            dp=self.stack.devices[self.rdid].port,)
        body = odict()
        packet = packeting.TxPacket(stack=self.stack,
                                    kind=raeting.pcktKinds.ack,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except raeting.PacketError as ex:
            print ex
            self.remove(self.rxPacket.index)
            return

        self.transmit(packet)

    def accept(self):
        '''
        Send accept response to join request
        '''
        if self.rdid not in self.stack.devices:
            emsg = "Invalid remote destination device id '{0}'".format(self.rdid)
            raise raeting.TransactionError(emsg)

        remote = self.stack.devices[self.rdid]

        body = odict([ ('ldid', self.rdid),
                       ('rdid', self.stack.device.did),
                       ('name', self.stack.device.name),
                       ('verhex', self.stack.device.signer.verhex),
                       ('pubhex', self.stack.device.priver.pubhex)])
        packet = packeting.TxPacket(stack=self.stack,
                                    kind=raeting.pcktKinds.response,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except raeting.PacketError as ex:
            print ex
            self.remove(self.rxPacket.index)
            return
        remote.joined = True # accepted
        remote.nextSid()
        self.transmit(packet)
        self.remove(self.rxPacket.index)

class Allower(Initiator):
    '''
    RAET protocol Allower Initiator class Dual of Allowent
    CurveCP handshake
    '''
    def __init__(self, **kwa):
        '''
        Setup instance
        '''
        kwa['kind'] = raeting.trnsKinds.allow
        super(Allower, self).__init__(**kwa)
        self.oreo = None # cookie from correspondent needed until handshake completed
        if self.rdid is None:
            self.rdid = self.stack.devices.values()[0].did # zeroth is channel master
        remote = self.stack.devices[self.rdid]
        if not remote.joined:
            emsg = "Must be joined first"
            raise raeting.TransactionError(emsg)
        remote.refresh() # refresh short term keys and .allowed
        self.sid = remote.sid
        self.tid = remote.nextTid()
        self.prep() # prepare .txData
        self.add(self.index)

    def receive(self, packet):
        """
        Process received packet belonging to this transaction
        """
        super(Allower, self).receive(packet) #  self.rxPacket = packet

        if packet.data['tk'] == raeting.trnsKinds.allow:
            if packet.data['pk'] == raeting.pcktKinds.cookie:
                self.cookie()
            elif packet.data['pk'] == raeting.pcktKinds.ack:
                self.allow()

    def prep(self):
        '''
        Prepare .txData
        '''
        remote = self.stack.devices[self.rdid]
        self.txData.update( sh=self.stack.device.host,
                            sp=self.stack.device.port,
                            dh=remote.host,
                            dp=remote.port,
                            sd=self.stack.device.did,
                            dd=self.rdid,
                            tk=self.kind,
                            cf=self.rmt,
                            bf=self.bcst,
                            si=self.sid,
                            ti=self.tid, )

    def hello(self):
        '''
        Send hello request
        '''
        if self.rdid not in self.stack.devices:
            emsg = "Invalid remote destination device id '{0}'".format(self.rdid)
            raise raeting.TransactionError(emsg)

        remote = self.stack.devices[self.rdid]
        plain = binascii.hexlify("".rjust(32, '\x00'))
        cipher, nonce = remote.privee.encrypt(plain, remote.pubber.key)
        body = raeting.HELLO_PACKER.pack(plain, remote.privee.pubraw, cipher, nonce)

        packet = packeting.TxPacket(stack=self.stack,
                                    kind=raeting.pcktKinds.hello,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except raeting.PacketError as ex:
            print ex
            self.remove()
            return
        self.transmit(packet)

    def cookie(self):
        '''
        Process cookie packet
        '''
        if not self.stack.parseInner(self.rxPacket):
            return
        data = self.rxPacket.data
        body = self.rxPacket.body.data

        if not isinstance(body, basestring):
            emsg = "Invalid format of cookie packet body"
            raise raeting.TransactionError(emsg)

        if len(body) != raeting.COOKIE_PACKER.size:
            emsg = "Invalid length of cookie packet body"
            raise raeting.TransactionError(emsg)

        cipher, nonce = raeting.COOKIE_PACKER.unpack(body)

        remote = self.stack.devices[self.rdid]

        msg = remote.privee.decrypt(cipher, nonce, remote.pubber.key)
        if len(msg) != raeting.COOKIESTUFF_PACKER.size:
            emsg = "Invalid length of cookie stuff"
            raise raeting.TransactionError(emsg)

        shortraw, sdid, ddid, oreo = raeting.COOKIESTUFF_PACKER.unpack(msg)

        if sdid != remote.did or ddid != self.stack.device.did:
            emsg = "Invalid sdid or ddid fields in cookie stuff"
            raeting.TransactionError(emsg)

        self.oreo = binascii.hexlify(oreo)
        remote.publee = nacling.Publican(key=shortraw)

        self.initiate()

    def initiate(self):
        '''
        Send initiate request to cookie response to hello request
        '''
        if self.rdid not in self.stack.devices:
            emsg = "Invalid remote destination device id '{0}'".format(self.rdid)
            raise raeting.TransactionError(emsg)

        remote = self.stack.devices[self.rdid]

        vcipher, vnonce = self.stack.device.priver.encrypt(remote.privee.pubraw,
                                                remote.pubber.key)

        fqdn = remote.fqdn.ljust(128, ' ')

        stuff = raeting.INITIATESTUFF_PACKER.pack(self.stack.device.priver.pubraw,
                                                  vcipher,
                                                  vnonce,
                                                  fqdn)

        cipher, nonce = remote.privee.encrypt(stuff, remote.publee.key)

        oreo = binascii.unhexlify(self.oreo)
        body = raeting.INITIATE_PACKER.pack(remote.privee.pubraw,
                                            oreo,
                                            cipher,
                                            nonce)

        packet = packeting.TxPacket(stack=self.stack,
                                    kind=raeting.pcktKinds.initiate,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except raeting.PacketError as ex:
            print ex
            self.remove()
            return

        self.transmit(packet)

    def allow(self):
        '''
        Process ackInitiate packet
        Perform allowment in response to ack to initiate packet
        '''
        if not self.stack.parseInner(self.rxPacket):
            return
        self.stack.devices[self.rdid].allowed = True
        self.remove()

class Allowent(Correspondent):
    '''
    RAET protocol Allowent Correspondent class Dual of Allower
    CurveCP handshake
    '''
    def __init__(self, **kwa):
        '''
        Setup instance
        '''
        kwa['kind'] = raeting.trnsKinds.allow
        if 'rdid' not  in kwa:
            emsg = "Missing required keyword argumens: '{0}'".format('rdid')
            raise TypeError(emsg)
        super(Allowent, self).__init__(**kwa)
        remote = self.stack.devices[self.rdid]
        if not remote.joined:
            emsg = "Must be joined first"
            raise raeting.TransactionError(emsg)
        #Current .sid was set by stack from rxPacket.data sid so it is the new rsid
        if not remote.validRsid(self.sid):
            emsg = "Stale sid '{0}' in packet".format(self.sid)
            raise raeting.TransactionError(emsg)
        remote.rsid = self.sid #update last received rsid for device
        remote.rtid = self.tid #update last received rtid for device
        self.oreo = None #keep locally generated oreo around for redos
        remote.refresh() # refresh short term keys and .allowed
        self.prep() # prepare .txData
        self.add(self.index)

    def receive(self, packet):
        """
        Process received packet belonging to this transaction
        """
        super(Allowent, self).receive(packet) #  self.rxPacket = packet

        if packet.data['tk'] == raeting.trnsKinds.allow:
            if packet.data['pk'] == raeting.pcktKinds.hello:
                self.hello()
            elif packet.data['pk'] == raeting.pcktKinds.initiate:
                self.initiate()

    def prep(self):
        '''
        Prepare .txData
        '''
        remote = self.stack.devices[self.rdid]
        self.txData.update( sh=self.stack.device.host,
                            sp=self.stack.device.port,
                            dh=remote.host,
                            dp=remote.port,
                            sd=self.stack.device.did,
                            dd=self.rdid,
                            tk=self.kind,
                            cf=self.rmt,
                            bf=self.bcst,
                            si=self.sid,
                            ti=self.tid, )

    def hello(self):
        '''
        Process hello packet
        '''
        if not self.stack.parseInner(self.rxPacket):
            return
        data = self.rxPacket.data
        body = self.rxPacket.body.data

        if not isinstance(body, basestring):
            emsg = "Invalid format of hello packet body"
            raise raeting.TransactionError(emsg)

        if len(body) != raeting.HELLO_PACKER.size:
            emsg = "Invalid length of hello packet body"
            raise raeting.TransactionError(emsg)

        plain, shortraw, cipher, nonce = raeting.HELLO_PACKER.unpack(body)

        remote = self.stack.devices[self.rdid]
        remote.publee = nacling.Publican(key=shortraw)
        msg = self.stack.device.priver.decrypt(cipher, nonce, remote.publee.key)
        if msg != plain :
            emsg = "Invalid plain not match decrypted cipher"
            raise raeting.TransactionError(emsg)

        self.cookie()

    def cookie(self):
        '''
        Send Cookie Packet
        '''
        if self.rdid not in self.stack.devices:
            emsg = "Invalid remote destination device id '{0}'".format(self.rdid)
            raise raeting.TransactionError(emsg)

        remote = self.stack.devices[self.rdid]
        oreo = self.stack.device.priver.nonce()
        self.oreo = binascii.hexlify(oreo)

        stuff = raeting.COOKIESTUFF_PACKER.pack(remote.privee.pubraw,
                                                self.stack.device.did,
                                                remote.did,
                                                oreo)

        cipher, nonce = self.stack.device.priver.encrypt(stuff, remote.publee.key)
        body = raeting.COOKIE_PACKER.pack(cipher, nonce)
        packet = packeting.TxPacket(stack=self.stack,
                                    kind=raeting.pcktKinds.cookie,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except raeting.PacketError as ex:
            print ex
            self.remove()
            return
        self.transmit(packet)

    def initiate(self):
        '''
        Process initiate packet
        '''
        if not self.stack.parseInner(self.rxPacket):
            return
        data = self.rxPacket.data
        body = self.rxPacket.body.data

        if not isinstance(body, basestring):
            emsg = "Invalid format of initiate packet body"
            raise raeting.TransactionError(emsg)

        if len(body) != raeting.INITIATE_PACKER.size:
            emsg = "Invalid length of initiate packet body"
            raise raeting.TransactionError(emsg)

        shortraw, oreo, cipher, nonce = raeting.INITIATE_PACKER.unpack(body)

        remote = self.stack.devices[self.rdid]

        if shortraw != remote.publee.keyraw:
            emsg = "Mismatch of short term public key in initiate packet"
            raise raeting.TransactionError(emsg)

        if (binascii.hexlify(oreo) != self.oreo):
            emsg = "Stale or invalid cookie in initiate packet"
            raise raeting.TransactionError(emsg)

        msg = remote.privee.decrypt(cipher, nonce, remote.publee.key)
        if len(msg) != raeting.INITIATESTUFF_PACKER.size:
            emsg = "Invalid length of initiate stuff"
            raise raeting.TransactionError(emsg)

        pubraw, vcipher, vnonce, fqdn = raeting.INITIATESTUFF_PACKER.unpack(msg)
        if pubraw != remote.pubber.keyraw:
            emsg = "Mismatch of long term public key in initiate stuff"
            raise raeting.TransactionError(emsg)

        fqdn = fqdn.rstrip(' ')
        if fqdn != self.stack.device.fqdn:
            emsg = "Mismatch of fqdn in initiate stuff"
            print emsg, fqdn, self.stack.device.fqdn
            raise raeting.TransactionError(emsg)

        vouch = self.stack.device.priver.decrypt(vcipher, vnonce, remote.pubber.key)
        if vouch != remote.publee.keyraw or vouch != shortraw:
            emsg = "Short term key vouch failed"
            raise raeting.TransactionError(emsg)


        self.ackInitiate()

    def ackInitiate(self):
        '''
        Send ack to initiate request
        '''
        if self.rdid not in self.stack.devices:
            msg = "Invalid remote destination device id '{0}'".format(self.rdid)
            raise raeting.TransactionError(msg)

        body = ""
        packet = packeting.TxPacket(stack=self.stack,
                                    kind=raeting.pcktKinds.ack,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except raeting.PacketError as ex:
            print ex
            self.remove()
            return

        self.transmit(packet)

        self.allow()

    def allow(self):
        '''
        Perform allowment
        '''
        self.stack.devices[self.rdid].allowed = True
        #self.remove()
        # keep around for 2 minutes to save cookie (self.oreo)

class Messenger(Initiator):
    '''
    RAET protocol Messenger Initiator class Dual of Messengent
    Generic messages
    '''
    def __init__(self, **kwa):
        '''
        Setup instance
        '''
        kwa['kind'] = raeting.trnsKinds.message
        super(Messenger, self).__init__(**kwa)
        self.segmentage = None # special packet to hold segments if any
        if self.rdid is None:
            self.rdid = self.stack.devices.values()[0].did # zeroth is channel master
        remote = self.stack.devices[self.rdid]
        if not remote.allowed:
            emsg = "Must be allowed first"
            raise raeting.TransactionError(emsg)
        self.sid = remote.sid
        self.tid = remote.nextTid()
        self.prep() # prepare .txData
        self.add(self.index)

    def receive(self, packet):
        """
        Process received packet belonging to this transaction
        """
        super(Messenger, self).receive(packet)

        if packet.data['tk'] == raeting.trnsKinds.message:
            if packet.data['pk'] == raeting.pcktKinds.ack:
                self.done()

    def prep(self):
        '''
        Prepare .txData
        '''
        remote = self.stack.devices[self.rdid]
        self.txData.update( sh=self.stack.device.host,
                            sp=self.stack.device.port,
                            dh=remote.host,
                            dp=remote.port,
                            sd=self.stack.device.did,
                            dd=self.rdid,
                            tk=self.kind,
                            cf=self.rmt,
                            bf=self.bcst,
                            si=self.sid,
                            ti=self.tid,)

    def message(self, body=None):
        '''
        Send message
        '''
        if self.rdid not in self.stack.devices:
            emsg = "Invalid remote destination device id '{0}'".format(self.rdid)
            raise raeting.TransactionError(emsg)

        if body is None:
            body = odict()

        packet = packeting.TxPacket(stack=self.stack,
                                    kind=raeting.pcktKinds.message,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except raeting.PacketError as ex:
            print ex
            self.remove()
            return
        if packet.segmented:
            self.segmentage = packet
            for segment in self.segmentage.segments.values():
                self.transmit(segment)
        else:
            self.transmit(packet)

    def done(self):
        '''
        Complete transaction and remove
        '''
        self.remove()

class Messengent(Correspondent):
    '''
    RAET protocol Messengent Correspondent class Dual of Messenger
    Generic Messages
    '''
    def __init__(self, **kwa):
        '''
        Setup instance
        '''
        kwa['kind'] = raeting.trnsKinds.message
        if 'rdid' not  in kwa:
            emsg = "Missing required keyword argumens: '{0}'".format('rdid')
            raise TypeError(emsg)
        super(Messengent, self).__init__(**kwa)
        self.segmentage = None # special packet to hold segments if any
        remote = self.stack.devices[self.rdid]
        if not remote.allowed:
            emsg = "Must be allowed first"
            raise raeting.TransactionError(emsg)
        #Current .sid was set by stack from rxPacket.data sid so it is the new rsid
        if not remote.validRsid(self.sid):
            emsg = "Stale sid '{0}' in packet".format(self.sid)
            raise raeting.TransactionError(emsg)
        remote.rsid = self.sid #update last received rsid for device
        remote.rtid = self.tid #update last received rtid for device
        self.prep() # prepare .txData
        self.add(self.index)

    def receive(self, packet):
        """
        Process received packet belonging to this transaction
        """
        super(Messengent, self).receive(packet)

        # resent message
        if packet.data['tk'] == raeting.trnsKinds.message:
            if packet.data['pk'] == raeting.pcktKinds.message:
                self.message()

    def prep(self):
        '''
        Prepare .txData
        '''
        remote = self.stack.devices[self.rdid]
        self.txData.update( sh=self.stack.device.host,
                            sp=self.stack.device.port,
                            dh=remote.host,
                            dp=remote.port,
                            sd=self.stack.device.did,
                            dd=self.rdid,
                            tk=self.kind,
                            cf=self.rmt,
                            bf=self.bcst,
                            si=self.sid,
                            ti=self.tid,)

    def message(self):
        '''
        Process message packet
        '''
        console.verbose("segment count = {0} tid={1}".format(
                 self.rxPacket.data['sc'], self.tid))
        if self.rxPacket.segmentive:
            if not self.segmentage:
                self.segmentage = packeting.RxPacket(stack=self.stack,
                                                data=self.rxPacket.data)
            self.segmentage.parseSegment(self.rxPacket)
            if not self.segmentage.desegmentable():
                return
            self.segmentage.desegmentize()
            if not self.stack.parseInner(self.segmentage):
                return
            body = self.segmentage.body.data
        else:
            if not self.stack.parseInner(self.rxPacket):
                return
            body = self.rxPacket.body.data

        self.stack.rxMsgs.append(body)
        self.ackMessage()

    def ackMessage(self):
        '''
        Send ack to message
        '''
        if self.rdid not in self.stack.devices:
            msg = "Invalid remote destination device id '{0}'".format(self.rdid)
            raise raeting.TransactionError(msg)

        body = odict()
        packet = packeting.TxPacket(stack=self.stack,
                                    kind=raeting.pcktKinds.ack,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except raeting.PacketError as ex:
            print ex
            self.remove()
            return
        self.transmit(packet)
        self.remove()

