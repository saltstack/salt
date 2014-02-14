# -*- coding: utf-8 -*-
'''
stacking.py raet protocol stacking classes
'''
# pylint: disable=W0611

# Import python libs
import socket

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
        self.timer = aiding.Timer(duration=self.timeout)
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

    def signature(self, msg):
        '''
        Return signature resulting from signing msg
        '''
        return (self.stack.device.signer.signature(msg))

    def verify(self, signature, msg):
        '''
        Return result of verifying msg with signature
        '''
        return (self.stack.devices[self.rid].verfer.verify(signature, msg))

    def encrypt(self, msg):
        '''
        Return (cipher, nonce) duple resulting from encrypting message
        with short term keys
        '''
        remote = self.stack.devices[self.rid]
        return (self.stack.device.privee.encrypt(msg, remote.publee.key))

    def decrypt(self, cipher, nonce):
        '''
        Return msg resulting from decrypting cipher and nonce
        with short term keys
        '''
        remote = remote = self.stack.devices[self.rid]
        return (self.stack.device.privee.decrypt(cipher, nonce, remote.publee, key))

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
    def __init__(self, **kwa):
        '''
        Setup Transaction instance
        '''
        kwa['kind'] = raeting.trnsKinds.join
        super(Joiner, self).__init__(**kwa)

        if self.rdid is None:
            if not self.stack.devices: # no channel master so make one
                master = devicing.RemoteDevice(did=0, ha=('127.0.0.1', raeting.RAET_PORT))
                self.stack.addRemoteDevice(master)

            self.rdid = self.stack.devices.values()[0].did # zeroth is channel master
        self.sid = 0
        self.tid = self.stack.devices[self.rdid].nextTid()
        self.add(self.index)

    def receive(self, packet):
        """
        Process received packet belonging to this transaction
        """
        super(Joiner, self).receive(packet)

        if packet.data['tk'] == raeting.trnsKinds.join:
            if packet.data['pk'] == raeting.pcktKinds.ack:
                self.pend()

            elif packet.data['pk'] == raeting.pcktKinds.response:
                self.accept()

    def join(self, body=None):
        '''
        Send join request
        '''
        body = body or odict()
        if self.rdid not in self.stack.devices:
            emsg = "Invalid remote destination device id '{0}'".format(self.rdid)
            raise raeting.TransactionError(emsg)

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
        body.update(verhex=self.stack.device.signer.verhex,
                    pubhex=self.stack.device.priver.pubhex)
        packet = packeting.TxPacket(transaction=self,
                                    kind=raeting.pcktKinds.request,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except packeting.PacketError as ex:
            print ex
            self.remove()
            return
        self.transmit(packet)

    def pend(self):
        '''
        Process ack to join packet
        '''
        #data = self.rxPacket.data
        #body = self.rxPacket.body.data
        #set timer for redo
        pass

    def accept(self):
        '''
        Perform acceptance in response to accept packt
        '''
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
            self.stack.moveRemoteDevice(remote.did, rdid)
        #self.stack.device.accepted = True
        remote.accepted = True
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
        # Since corresponding bootstrap transaction use packet.index not self.index
        self.add(self.rxPacket.index)

    def pend(self):
        '''
        Perform pend operation of pending device being accepted onto channel
        '''
        data = self.rxPacket.data
        body = self.rxPacket.body.data

        # need to add search for existing device with same host,port address

        device = devicing.RemoteDevice(stack=self.stack,
                              host=data['sh'],
                              port=data['sp'],
                              rsid=self.sid,
                              rtid=self.tid, )
        self.stack.addRemoteDevice(device) #provisionally add .accepted is None

        self.rdid = device.did

        verhex = body.get('verhex')
        if not verhex:
            emsg = "Missing remote verifier key in join packet"
            raise raeting.TransactionError(emsg)

        pubhex = body.get('pubhex')
        if not pubhex:
            emsg = "Missing remote crypt key in join packet"
            raise raeting.TransactionError(emsg)

        device.verfer = nacling.Verifier(key=verhex)
        device.pubber = nacling.Publican(key=pubhex)

        self.ackJoin()

    def ackJoin(self, body=None):
        '''
        Send ack to join request
        '''
        body = body or odict()
        if self.rdid not in self.stack.devices:
            emsg = "Invalid remote destination device id '{0}'".format(self.rdid)
            raise raeting.TransactionError(emsg)

        #since bootstrap transaction use the reversed sdid and ddid from packet
        self.txData.update( sh=self.stack.device.host,
                            sp=self.stack.device.port,
                            dh=self.stack.devices[self.rdid].host,
                            dp=self.stack.devices[self.rdid].port,
                            sd=self.rxPacket.data['dd'],
                            dd=self.rxPacket.data['sd'],
                            tk=self.kind,
                            cf=self.rmt,
                            bf=self.bcst,
                            si=self.sid,
                            ti=self.tid,
                            ck=raeting.coatKinds.nada,
                            fk=raeting.footKinds.nada,)
        body.update()
        packet = packeting.TxPacket(transaction=self,
                                    kind=raeting.pcktKinds.ack,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except packeting.PacketError as ex:
            print ex
            self.remove(self.rxPacket.index)
            return

        self.transmit(packet)

    def accept(self, body=None):
        '''
        Send accept response to join request
        '''
        body = body or odict()
        if self.rdid not in self.stack.devices:
            emsg = "Invalid remote destination device id '{0}'".format(self.rdid)
            raise raeting.TransactionError(emsg)

        remote = self.stack.devices[self.rdid]
        #since bootstrap transaction use the reversed sdid and ddid from packet
        self.txData.update( sh=self.stack.device.host,
                            sp=self.stack.device.port,
                            dh=remote.host,
                            dp=remote.port,
                            sd=self.rxPacket.data['dd'],
                            dd=self.rxPacket.data['sd'],
                            tk=self.kind,
                            cf=self.rmt,
                            bf=self.bcst,
                            si=self.sid,
                            ti=self.tid,
                            ck=raeting.coatKinds.nada,
                            fk=raeting.footKinds.nada,)
        body.update( ldid=self.rdid,
                     rdid=self.stack.device.did,
                     verhex=self.stack.device.signer.verhex,
                     pubhex=self.stack.device.priver.pubhex,)
        packet = packeting.TxPacket(transaction=self,
                                    kind=raeting.pcktKinds.response,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except packeting.PacketError as ex:
            print ex
            self.remove(self.rxPacket.index)
            return
        remote.accepted = True
        self.transmit(packet)
        self.remove(self.rxPacket.index)

class Endower(Initiator):
    '''
    RAET protocol Endower Initiator class Dual of Endowent
    CurveCP handshake
    '''
    def __init__(self, **kwa):
        '''
        Setup instance
        '''
        kwa['kind'] = raeting.trnsKinds.endow
        super(Endower, self).__init__(**kwa)
        self.oreo = None # cookie from correspondent needed until handshake completed
        if self.rdid is None:
            self.rdid = self.stack.devices.values()[0].did # zeroth is channel master
        remote = self.stack.devices[self.rdid]
        if not remote.accepted:
            emsg = "Must be accepted first"
            raise raeting.TransactionError(emsg)
        remote.refresh() # refresh short term keys and .endowed
        self.sid = remote.sid
        self.tid = remote.nextTid()
        self.prep() # prepare .txData
        self.add(self.index)

    def receive(self, packet):
        """
        Process received packet belonging to this transaction
        """
        super(Endower, self).receive(packet)

        if packet.data['tk'] == raeting.trnsKinds.endow:
            if packet.data['pk'] == raeting.pcktKinds.cookie:
                self.initiate()
            elif packet.data['pk'] == raeting.pcktKinds.ack:
                self.endow()

    def prep(self):
        '''
        Prepare .txData
        '''
        remote = self.stack.devices[self.rid]
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
                            ti=self.tid,
                            ck=raeting.coatKinds.nada,
                            fk=raeting.footKinds.nacl)

    def hello(self, body=None):
        '''
        Send hello request
        '''
        body = body or odict()
        if self.rdid not in self.stack.devices:
            emsg = "Invalid remote destination device id '{0}'".format(self.rdid)
            raise raeting.TransactionError(emsg)

        remote = self.stack.devices[self.rid]
        msg = "".rjust(64, '\x00'),
        cypher, nonce = remote.privlee.encrypt(msg, remote.pubber.key)
        body.update(plain=msg,
                    shorthex=remote.privee.pubhex,
                    cypher=cypher,
                    nonce=nonce)
        packet = packeting.TxPacket(transaction=self,
                                    kind=raeting.pcktKinds.hello,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except packeting.PacketError as ex:
            print ex
            self.remove()
            return
        self.transmit(packet)

    def cookie(self):
        '''
        Process cookie packet
        '''
        data = self.rxPacket.data
        body = self.rxPacket.body.data

        cipher = body.get('cipher')
        if not cipher:
            emsg = "Missing cipher in cookie packet"
            raise raeting.TransactionError(emsg)

        nonce = body.get('nonce')
        if not nonce:
            emsg = "Missing nonce in cookie packet"
            raise raeting.TransactionError(emsg)

        remote = self.stack.devices[self.rdid]

        msg = remote.privee.decrypt(cipher, nonce, remote.pubber.key)
        stuff = json.loads(msg, object_pairs_hook=odict)

        shorthex= stuff.get('shorthex')
        if not shorthex:
            emsg = "Missing short term key in cookie"
            raise raeting.TransactionError(emsg)


        if stuff.get('sdid') != remote.did or self.get('ddid') != self.stack.device.did:
            emsg = "Invalid cookie  sdid or ddid fields in cookie packet"
            raeting.TransactionError(emsg)

        oreo = stuff.get('oreo')
        if not oreo:
            emsg = "Missing cookie nonce in cookie packet"
            raeting.TransactionError(emsg)

        self.oreo = oreo
        remote.publee = nacling.Publican(key=shorthex)

        self.initiate()

    def initiate(self, body=None):
        '''
        Send initiate request to cookie response to hello request
        '''
        body = body or odict()
        if self.rdid not in self.stack.devices:
            emsg = "Invalid remote destination device id '{0}'".format(self.rdid)
            raise raeting.TransactionError(emsg)

        remote = self.stack.devices[self.rid]
        vouch = json.dumps(odict(shorthex=remote.privee.pubhex), separators=(',', ':'))
        vcipher, vnonce = self.stack.device.priver.encrypt(vouch, remote.pubber.key)
        stuff = odict(longhex=self.stack.device.priver.keyhex,
                      vcipher=vcipher,
                      vnonce=vnonce,
                      fqdn=remote.fqdn)
        cipher, nonce = remote.privee.encrypt(stuff, remote.publee.key)
        body.update(shorthex=remote.privee.pubhex,
                    oreo=self.oreo,
                    cipher=cipher,
                    nonce=nonce,)
        packet = packeting.TxPacket(transaction=self,
                                    kind=raeting.pcktKinds.initiate,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except packeting.PacketError as ex:
            print ex
            self.remove()
            return

        self.transmit(packet)

    def endow(self):
        '''
        Perform endowment in response to ack to initiate packet
        '''
        self.stack.devices[self.rid].endowed = True
        self.remove()

class Endowent(Correspondent):
    '''
    RAET protocol Endowent Correspondent class Dual of Endower
    CurveCP handshake
    '''
    def __init__(self, **kwa):
        '''
        Setup instance
        '''
        kwa['kind'] = raeting.trnsKinds.endow
        if 'rid' not  in kwa:
            emsg = "Missing required keyword argumens: '{0}'".format('rid')
            raise TypeError(emsg)
        super(Endowent, self).__init__(**kwa)
        remote = self.stack.devices[self.rdid]
        if not remote.accepted:
            emsg = "Must be accepted first"
            raise raeting.TransactionError(emsg)
        self.oreo = None #keep locally generated oreo around for redos
        remote.refresh() # refresh short term keys and .endowed
        self.prep() # prepare .txData
        self.add(self.index)

    def receive(self, packet):
        """
        Process received packet belonging to this transaction
        """
        super(Endowent, self).receive(packet)

        if packet.data['tk'] == raeting.trnsKinds.endow:
            if packet.data['pk'] == raeting.pcktKinds.hello:
                self.hello()
            elif packet.data['pk'] == raeting.pcktKinds.initiate:
                self.initiate()

    def prep(self):
        '''
        Prepare .txData
        '''
        remote = self.stack.devices[self.rid]
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
                            ti=self.tid,
                            ck=raeting.coatKinds.nada,
                            fk=raeting.footKinds.nacl)

    def hello(self):
        '''
        Process hello packet
        '''
        data = self.rxPacket.data
        body = self.rxPacket.body.data

        plain = body.get('plain')
        if not plain:
            emsg = "Missing plain in hello packet"
            raise raeting.TransactionError(emsg)

        if len(plain) != 64:
            emsg = "Invalid plain size = {0}".format(len(plain))
            raise raeting.TransactionError(emsg)

        shorthex = body.get('shorthex')
        if not shorthex:
            emsg = "Missing shorthex in hello packet"
            raise raeting.TransactionError(emsg)

        cipher = body.get('cipher')
        if not cipher:
            emsg = "Missing cipher in hello packet"
            raise raeting.TransactionError(emsg)

        nonce = body.get('nonce')
        if not nonce:
            emsg = "Missing nonce in hello packet"
            raise raeting.TransactionError(emsg)

        remote = self.stack.devices[self.rdid]
        remote.publee = nacling.Publican(key=shorthex)
        msg = remote.publee.decrypt(cipher, nonce, remote.pubber.key)
        if msg != plain :
            emsg = "Invalid plain not match decrypted cipher"
            raise raeting.TransactionError(emsg)

        self.cookie()

    def cookie(self, body=None):
        '''
        Send Cookie Packet
        '''
        body = body or odict()
        if self.rdid not in self.stack.devices:
            emsg = "Invalid remote destination device id '{0}'".format(self.rdid)
            raise raeting.TransactionError(emsg)

        remote = self.stack.devices[self.rid]
        self.oreo = remote.priver.nonce()

        stuff = odict(  shorthex=remote.privee.pubhex,
                        sdid=self.stack.devices.did,
                        ddid=remote.did,
                        oreo=self.oreo)
        stuff = json.dumps(stuff, separators=(',', ':'))

        cipher, nonce = self.priver.encrypt(stuff, remote.publee.key)
        body.update(cipher=cipher, nonce=nonce,)
        packet = packeting.TxPacket(transaction=self,
                                    kind=raeting.pcktKinds.cookie,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except packeting.PacketError as ex:
            print ex
            self.remove()
            return
        self.transmit(packet)

    def initiate(self):
        '''
        Process initiate packet
        '''
        data = self.rxPacket.data
        body = self.rxPacket.body.data

        shorthex
        oreo
        cipher
        nonce

        plain = body.get('plain')
        if not plain:
            emsg = "Missing plain in hello packet"
            raise raeting.TransactionError(emsg)

        if len(plain) != 64:
            emsg = "Invalid plain size = {0}".format(len(plain))
            raise raeting.TransactionError(emsg)

        shorthex = body.get('shorthex')
        if not shorthex:
            emsg = "Missing shorthex in hello packet"
            raise raeting.TransactionError(emsg)

        cipher = body.get('cipher')
        if not cipher:
            emsg = "Missing cipher in hello packet"
            raise raeting.TransactionError(emsg)

        nonce = body.get('nonce')
        if not nonce:
            emsg = "Missing nonce in hello packet"
            raise raeting.TransactionError(emsg)

        remote = self.stack.devices[self.rdid]
        remote.publee = nacling.Publican(key=shorthex)
        msg = remote.publee.decrypt(cipher, nonce, remote.pubber.key)
        if msg != plain :
            emsg = "Invalid plain not match decrypted cipher"
            raise raeting.TransactionError(emsg)

        self.cookie()

    def ackInitiate(self, body=None):
        '''
        Send ack to initiate request
        '''
        body = body or odict()
        if self.rdid not in self.stack.devices:
            msg = "Invalid remote destination device id '{0}'".format(self.rdid)
            raise raeting.TransactionError(msg)

        body.update()
        packet = packeting.TxPacket(transaction=self,
                                    kind=raeting.pcktKinds.ack,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except packeting.PacketError as ex:
            print ex
            self.remove()
            return

        self.endow()

    def endow(self):
        '''
        Perform endowment
        '''
        self.stack.devices[self.rid].endowed = True
        #self.remove()
        # keep around for 2 minutes to save cookie (self.oreo)