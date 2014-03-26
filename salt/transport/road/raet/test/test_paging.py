# -*- coding: utf-8 -*-
'''
Tests to try out paging. Potentially ephemeral

'''
# pylint: skip-file
# pylint: disable=C0103

import os

from ioflo.base.odicting import odict
from ioflo.base.aiding import Timer, StoreTimer
from ioflo.base import storing

from ioflo.base.consoling import getConsole
console = getConsole()

from salt.transport.road.raet import (raeting, nacling, paging, keeping,
                                      yarding, stacking)


def test( pk=raeting.packKinds.json):
    '''
    Test paging.
    '''
    console.reinit(verbosity=console.Wordage.concise)

    #data = odict(hk=hk, bk=bk)
    body = odict(raeting.PAGE_DEFAULTS)
    page0 = paging.TxPage(kind=pk, data=body)
    print page0.data
    page0.pack()
    print len(page0.packed)
    print page0.packed
    page1 = paging.RxPage(packed=page0.packed)
    page1.parse()
    print page1.data

    stuff = []
    for i in range(10000):
        stuff.append(str(i).rjust(10, " "))
    stuff = "".join(stuff)
    body = odict(msg=stuff)
    page0 = paging.TxPage(kind=pk, data=body)
    try:
        page0.pack()
    except raeting.PageError as ex:
        print ex
        print "Need to use book"

    data = odict(syn="boy", dyn='girl', mid=1)
    book0 = paging.TxBook(data=data, body=body, kind=pk)
    book0.pack()
    print book0.packed
    print book0.pages

    book1 = paging.RxBook()
    for page in book0.pages:
        page = paging.RxPage(packed=page.packed)
        page.parse()
        book1.parse(page)

    print book1.data
    print book1.body

    print body == book1.body

    stacking.StackUxd.Pk = pk
    store = storing.Store(stamp=0.0)

    #lord stack
    stack0 = stacking.StackUxd(store=store)

    #serf stack
    stack1 = stacking.StackUxd(store=store)

    stack0.addRemoteYard(yarding.RemoteYard(ha=stack1.yard.ha))
    stack1.addRemoteYard(yarding.RemoteYard(ha=stack0.yard.ha))

    print "{0} yard name={1} ha={2}".format(stack0.name, stack0.yard.name, stack0.yard.ha)
    print "{0} yards=\n{1}".format(stack0.name, stack0.yards)
    print "{0} names=\n{1}".format(stack0.name, stack0.names)

    print "{0} yard name={1} ha={2}".format(stack1.name, stack1.yard.name, stack1.yard.ha)
    print "{0} yards=\n{1}".format(stack1.name, stack1.yards)
    print "{0} names=\n{1}".format(stack1.name, stack1.names)

    print "\n____________ Messaging through stack tests "

    msg = odict(stuff=stuff)
    stack0.transmit(msg=body)

    msg = odict(what="This is a message to the serf. Get to Work", extra="Fix the fence.")
    stack0.transmit(msg=msg)

    msg = odict(what="This is a message to the lord. Let me be", extra="Go away.")
    stack1.transmit(msg=msg)



    timer = Timer(duration=0.5)
    timer.restart()
    while not timer.expired or store.stamp < 1.0:
        stack0.serviceAll()
        stack1.serviceAll()
        store.advanceStamp(0.1)

    print "{0} Received Messages".format(stack0.name)
    for msg in stack0.rxMsgs:
        print msg
    print

    print "{0} Received Messages".format(stack1.name)
    for msg in stack1.rxMsgs:
        print msg
    print


    stack0.server.close()
    stack1.server.close()


if __name__ == "__main__":
    test(pk=raeting.packKinds.pack)
    test(pk=raeting.packKinds.json)

