# -*- coding: utf-8 -*-
#pylint: skip-file
'''
paging module provides classes for RAET UXD messaging management

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

from ioflo.base.consoling import getConsole
console = getConsole()

from . import raeting


class Page(object):
    '''
    RAET UXD protocol page object. Support sectioning of messages into Uxd pages
    '''
    Pk = raeting.packKinds.json

    def __init__(self, stack=None, data=None, kind=None):
        ''' Setup Page instance. Meta data for a packet. '''
        self.stack = stack
        self.data = data or odict()
        self.kind = kind if kind is not None else self.Pk
        if self.kind not in [raeting.packKinds.json, raeting.packKinds.pack]:
            emsg = "Invalid message pack kind '{0}'\n".format(kind)
            console.terse(emsg)
            raise raeting.PageError(emsg)
        self.packed = ''  # packed string
        self.head = ''
        self.body = ''

    @property
    def size(self):
        '''
        Property is the length of the .packed of this page
        '''
        return len(self.packed)

    @property
    def paginated(self):
        '''
        Property is True if the page data as 'page' field else false
        '''
        return (True if self.data.get('page') else False)

class TxPage(Page):
    '''
    RAET Protocol Transmit Page object
    '''
    def __init__(self, data=None, **kwa):
        '''
        Setup TxPacket instance
        '''
        super(TxPage, self).__init__(**kwa)
        if data is not None:
            self.data.update(data)

    @property
    def index(self):
        '''
        Property is unique message tuple (lyn, ryn, mid)
        If not paginated return (None, None, 0)
        lyn = local yard name which for transmit is syn
        ryn = remote yard name which for transmit is dyn
        mid = message id
        '''
        data = self.data.get('page', odict(syn=None, dyn=None, mid=0))
        return (data['syn'], data['dyn'], data['mid'], )

    def prepack(self):
        '''
        Pack serialize message body data
        '''
        self.packed = ''
        self.head = ''
        self.body = ''

        if self.kind == raeting.packKinds.json:
            self.head = 'RAET\njson\n\n'
            self.body = json.dumps(self.data, separators=(',', ':'))
            self.packed = "".join([self.head, self.body])

        elif self.kind == raeting.packKinds.pack:
            if not msgpack:
                emsg = "Msgpack not installed\n"
                console.terse(emsg)
                raise raeting.PageError(emsg)
            self.head = 'RAET\npack\n\n'
            self.body = msgpack.dumps(self.data)
            self.packed = "".join([self.head, self.body ])

    def pack(self):
        '''
        Pack serialize message body data and check for size limit
        '''
        self.prepack()

        if self.size > raeting.UXD_MAX_PACKET_SIZE: #raeting.MAX_MESSAGE_SIZE
            emsg = "Message length of {0}, exceeds max of {1}\n".format(
                     self.size, raeting.UXD_MAX_PACKET_SIZE)
            console.terse(emsg)
            raise raeting.PageError(emsg)

class RxPage(Page):
    '''
    RAET Protocol Receive Page object
    '''
    def __init__(self, packed=None, **kwa):
        '''
        Setup RxPage instance
        '''
        super(RxPage, self).__init__(**kwa)
        self.packed = packed or ''

    @property
    def index(self):
        '''
        Property is unique message tuple (lyn, ryn, mid)
        If not paginated return (None, None, 0)
        lyn = local yard name which for receive is dyn
        ryn = remote yard name which for receive is syn
        mid = message id
        '''
        data = self.data.get('page', odict(syn=None, dyn=None, mid=0))
        return (data['dyn'], data['syn'], data['mid'], )

    def parseHead(self, packed=None):
        '''
        Parse head of message in packed or self.packed
        '''
        if packed:
            self.packed = packed

        if not self.packed:
            emsg = "Packed empty, nothing to parse."
            console.terse(emsg)
            raise raeting.PageError(emsg)

        if (not self.packed.startswith('RAET\n') or raeting.HEAD_END not in self.packed):
            emsg = "Unrecognized packed body head\n"
            console.terse(emsg)
            raise raeting.PageError(emsg)

        front, sep, back = self.packed.partition(raeting.HEAD_END)
        code, sep, kind = front.partition('\n')
        if kind not in [raeting.PACK_KIND_NAMES[raeting.packKinds.json],
                        raeting.PACK_KIND_NAMES[raeting.packKinds.pack]]:
            emsg = "Unrecognized message pack kind '{0}'\n".format(kind)
            console.terse(emsg)
            raise raeting.PageError(emsg)

        if len(back) > raeting.UXD_MAX_PACKET_SIZE: #raeting.MAX_MESSAGE_SIZE
            emsg = "Message length of {0}, exceeds max of {1}\n".format(
                     len(back), raeting.UXD_MAX_PACKET_SIZE)
            console.terse(emsg)
            raise raeting.PageError(emsg)

        self.kind = raeting.PACK_KINDS[kind]
        self.head = front + sep
        self.body = back

    def parseBody(self):
        self.data = odict()

        if self.kind == raeting.packKinds.json:
            self.data = json.loads(self.body, object_pairs_hook=odict)

        elif self.kind == raeting.packKinds.pack:
            if not msgpack:
                emsg = "Msgpack not installed\n"
                console.terse(emsg)
                raise raeting.PageError(emsg)
            self.data = msgpack.loads(self.body, object_pairs_hook=odict)

        if not isinstance(self.data, Mapping):
            emsg = "Message body not a mapping\n"
            console.terse(emsg)
            raise raeting.PageError(emsg)

    def parse(self, packed=None):
        '''
        Parse (deserialize message) result in self.data
        '''
        if packed:
            self.packed = packed

        self.parseHead(packed)
        self.parseBody()

class Book(object):
    '''
    Manages messages, sectioning when needed and the associated pages
    '''
    def __init__(self, stack=None, data=None, body=None, kind=None, **kwa):
        '''
        Setup instance
        '''
        self.stack = stack
        self.data = odict(raeting.PAGE_DEFAULTS)
        if data:
            self.data.update(data)
        self.body = body #body data of message
        self.kind = kind
        self.packed = ''

    @property
    def size(self):
        '''
        Property is the length of the .packed
        '''
        return len(self.packed)

class TxBook(Book):
    '''
    Manages an outgoing message and its associated pages(s)
    '''
    def __init__(self, **kwa):
        '''
        Setup instance
        '''
        super(TxBook, self).__init__(**kwa)
        self.pages = []

    @property
    def index(self):
        '''
        Property is unique message tuple (ryn, lyn, mid)
        ryn = remote yard name which for transmit is syn
        lyn = local yard name which for transmit is dyn
        mid = message id
        '''
        return (self.data['syn'], self.data['dyn'], self.data['mid'],)

    def pack(self, data=None, body=None):
        '''
        Convert message in .body into one or more pages
        '''
        self.packed = ''
        if data:
            self.data.update(data)
        if body is not None:
            self.body = body

        self.current = 0
        self.pages = []
        page = TxPage(  stack=self.stack,
                        data=self.body,
                        kind=self.kind)

        page.prepack()
        if page.size <= raeting.UXD_MAX_PACKET_SIZE:
            self.pages.append(page)
        else:
            self.packed = page.body
            self.paginate(headsize=len(page.head))

    def paginate(self, headsize):
        '''
        Create packeted segments from .packed using headsize
        '''
        if self.kind == raeting.packKinds.json:
            extrasize = 4096 #need better estimate
        else:
            extrasize = 2048

        hotelsize = headsize + extrasize
        secsize = raeting.UXD_MAX_PACKET_SIZE - hotelsize

        seccount = (self.size // secsize) + (1 if self.size % secsize else 0)
        for i in range(seccount):
            if i == seccount - 1: #last section
                section = self.packed[i * secsize:]
            else:
                section = self.packed[i * secsize: (i+1) * secsize]
            data = odict(self.data)
            data['number'] = i
            data['count'] = seccount
            data['section'] = section
            page = TxPage( stack=self.stack, data=odict(page=data), kind=self.kind)
            page.pack()
            self.pages.append(page)


class RxBook(Book):
    '''
    Manages sectioned messages and the associated pages
    '''
    def __init__(self, sections=None, **kwa):
        '''
        Setup instance
        '''
        super(RxBook, self).__init__(**kwa)
        self.sections = sections if sections is not None else []
        self.complete = False

    @property
    def index(self):
        '''
        Property is unique message tuple (lyn, ryn, mid)
        lyn = local yard name which for receive is dyn
        ryn = remote yard name which for receive is syn
        mid = message id
        '''
        return (self.data['dyn'], self.data['syn'], self.data['mid'], )

    def parse(self, page):
        '''
        Process a given page. Assumes its already been parsed
        '''
        self.kind = page.kind

        if not page.paginated: # not a paginated message
            self.body = page.data
            self.complete = True
            return self.body

        data = page.data['page']
        count = data['count']
        console.verbose("section count = {0} mid={1}\n".format(count, data['mid']))

        if not self.sections: #update data from first page received
            self.data.update(data)
            self.sections = [None] * count

        section = data['section']
        number = data['number']

        self.sections[number] = section
        if None in self.sections: #don't have all sections yet
            return None
        self.body = self.desectionize()
        return self.body

    def desectionize(self):
        '''
        Generate message from pages
        '''
        count = self.data['count']
        self.packed = "".join(self.sections)

        page = RxPage(stack = self.stack, kind=self.kind)
        page.body = self.packed
        page.parseBody()
        self.complete = True

        return page.data


