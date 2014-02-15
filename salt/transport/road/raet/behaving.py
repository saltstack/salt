# -*- coding: utf-8 -*-
'''
behaving.py raet ioflo behaviors

See raeting.py for data format and packet field details.

Data format. The data from which a packet is created is a nested dict of dicts.
What fields are included in a packed head, neck, body is dependent
on the header kind, service kind, packet kind and defaults.
To minimize lenght of JSON headers if field missing then the default is assumed

data =
{
    meta: dict of meta data about packet
    {

    }
    head: dict of header fields
    {
        pack: packed version of header
    }
    neck: dict of authentication fields
    {
        pack: packed version of neck
    }
    body: dict of body fields
    {
        pack: packed version of body
    }
    pack: packed version of whole packet on tx and raw packet on rx

}
'''
# pylint: skip-file
# pylint: disable=W0611

# Import Python libs
from collections import deque
try:
    import simplejson as json
except ImportError:
    import json

# Import ioflo libs
from ioflo.base.odicting import odict
from ioflo.base.globaling import *

from ioflo.base import aiding
from ioflo.base import storing
from ioflo.base import deeding

from ioflo.base.consoling import getConsole
console = getConsole()

from . import raeting


class ComposerRaet(deeding.ParamDeed):  # pylint: disable=W0232
    '''
    ComposerRaet creates packet data as nested dicts from fields in
    share parms meta, head, neck, body, tail

    inherited attributes
        .name is actor name string
        .store is data store ref
        .ioinits is dict of io init data for initio
        ._parametric is flag for initio to not create attributes
    '''
    Ioinits = odict(
        data=odict(ipath='data', ival=odict(), iown='True'),
        meta='meta',
        head='head',
        neck='neck',
        body='body',
        tail='tail')

    def action(self, data, meta, head, neck, body, tail, **kwa):
        '''
        Build packet data from data section shares
        '''
        dat = raeting.defaultData()
        dat['meta'].update(raeting.META_DEFAULTS)
        dat['meta'].update(meta.items())
        dat['head'].update(raeting.HEAD_DEFAULTS)
        dat['head'].update(head.items())
        dat['neck'].update(neck.items())
        dat['body'].update(data=odict(body.items()))
        dat['tail'].update(tail.items())
        data.value = dat
        return None


class PackerRaet(deeding.ParamDeed):  # pylint: disable=W0232
    '''
    PackerRaet creates a new packed RAET packet from data and fills in pack field

    inherited attributes
        .name is actor name string
        .store is data store ref
        .ioinits is dict of io init data for initio
        ._parametric is flag for initio to not create attributes
    '''
    Ioinits = odict(
        data=odict(ipath='data', ival=odict(), iown=True),
        outlog=odict(ipath='outlog', ival=odict(), iown=True),)

    def action(self, data, outlog, **kwa):
        """ Build packet from data"""
        if data.value:
            raeting.packPacket(data.value)
            data.stampNow()
            outlog.value[(data.value['meta']['dh'], data.value['meta']['dp'])] = data.value['body'].get('data', {})
        return None


class ParserRaet(deeding.ParamDeed):  # pylint: disable=W0232
    '''
    ParserRaet parses a packed RAET packet from pack and fills in data

    inherited attributes
        .name is actor name string
        .store is data store ref
        .ioinits is dict of io init data for initio
        ._parametric is flag for initio to not create attributes
    '''
    Ioinits = odict(
        data=odict(ipath='data', ival=odict(), iown=True),
        inlog=odict(ipath='inlog', ival=odict(), iown=True),)

    def action(self, data, inlog, **kwa):
        """ Parse packet from raw packed"""
        if data.value:
            data.value = raeting.defaultData(data.value)
            rest = raeting.parsePacket(data.value)
            data.stampNow()
            inlog.value[(data.value['meta']['sh'], data.value['meta']['sp'])] = data.value['body'].get('data', {})
        return None


class TransmitterRaet(deeding.ParamDeed):  # pylint: disable=W0232
    '''
    TransmitterRaet pushes packed packet in onto txes transmit deque and assigns
    destination ha from meta data

    inherited attributes
        .name is actor name string
        .store is data store ref
        .ioinits is dict of io init data for initio
        ._parametric is flag for initio to not create attributes
    '''
    Ioinits = odict(
        data='data',
        txes=odict(ipath='.raet.media.txes', ival=deque()),)

    def action(self, data, txes, **kwa):
        '''
        Transmission action
        '''
        if data.value:
            da = (data.value['meta']['dh'], data.value['meta']['dp'])
            txes.value.append((data.value['pack'], da))
        return None


class ReceiverRaet(deeding.ParamDeed):  # pylint: disable=W0232
    '''
    ReceiverRaet pulls packet from rxes deque and puts into new data
    and assigns meta data source ha using received ha

    inherited attributes
        .name is actor name string
        .store is data store ref
        .ioinits is dict of io init data for initio
        ._parametric is flag for initio to not create attributes
    '''
    Ioinits = odict(
            data='data',
            rxes=odict(ipath='.raet.media.rxes', ival=deque()), )

    def action(self, data, rxes, **kwa):
        '''
        Handle recived packet
        '''
        if rxes.value:
            rx, sa, da = rxes.value.popleft()
            data.value = raeting.defaultData()
            data.value['pack'] = rx
            data.value['meta']['sh'], data.value['meta']['sp'] = sa
            data.value['meta']['dh'], data.value['meta']['dp'] = da
        return None


class ServerRaet(deeding.ParamDeed):  # pylint: disable=W0232
    '''
    ServerRaet transmits and recieves udp packets from txes and rxes deques
    using sh, sp fields in sa server address (server host, server port) to receive on.
    Server is nonblocking socket connection

    inherited attributes
        .name is actor name string
        .store is data store ref
        .ioinits is dict of io init data for initio
        ._parametric is flag for initio to not create attributes
    '''
    Ioinits = odict(
        txes=odict(ipath='txes', ival=deque(), iown=True),
        rxes=odict(ipath='rxes', ival=deque(), iown=True),
        connection=odict(ipath='connection', ival=None, iown=True),
        address=odict(ipath='address', ival=odict(host='', port=7530, ha=None)),
        txlog=odict(ipath='txlog', ival=odict(), iown=True),
        rxlog=odict(ipath='rxlog', ival=odict(), iown=True), )

    def postinitio(self, connection, address, **kwa):
        '''
        Set up server to transmit and recive on address
        '''
        connection.value = aiding.SocketUdpNb(host=address.data.host, port=address.data.port)
        connection.value.reopen()  # create socket connection
        host, port = connection.value.ha
        address.update(host=host, port=port, ha=(host, port))
        return None

    def action(self, txes, rxes, connection, address, txlog, rxlog, **kwa):
        '''
        Receive any udp packets on server socket and put in rxes
        Send any packets in txes
        '''
        server = connection.value
        txl = txlog.value
        rxl = rxlog.value

        if server:
            rxds = rxes.value
            while True:
                rx, ra = server.receive()  # if no data the tuple is ('',None)
                if not rx:  # no received data so break
                    break
                rxds.append((rx, ra, address.data.ha))
                rxl[ra] = rx

            txds = txes.value
            while txds:
                tx, ta = txds.popleft()
                server.send(tx, ta)
                txl[ta] = tx
        return None


class CloserServerRaet(deeding.ParamDeed):  # pylint: disable=W0232
    '''
    CloserServerRaet closes server socket connection

    inherited attributes
        .name is actor name string
        .store is data store ref
        .ioinits is dict of io init data for initio
        ._parametric is flag for initio to not create attributes
    '''
    Ioinits = odict(
        connection=odict(ipath='connection', ival=None))

    def action(self, connection, **kwa):
        '''
        Receive any udp packets on server socket and put in rxes
        Send any packets in txes
        '''
        if connection.value:
            connection.value.close()
        return None
