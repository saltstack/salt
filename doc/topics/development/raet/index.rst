raet
====

# RAET
# Reliable Asynchronous Event Transport Protocol

.. seealso:: :ref:`RAET Overview <raet>`

Protocol
--------

Layering:

OSI Layers

7: Application: Format: Data (Stack to Application interface buffering etc)
6: Presentation: Format: Data (Encrypt-Decrypt convert to machine independent format)
5: Session: Format: Data (Interhost communications. Authentication. Groups)
4: Transport: Format: Segments (Reliable delivery of Message, Transactions, Segmentation, Error checking)
3: Network: Format: Packets/Datagrams (Addressing Routing)
2: Link: Format: Frames ( Reliable per frame communications connection, Media access controller )
1: Physical: Bits (Transceiver communication connection not reliable)

Link is hidden from Raet
Network is IP host address and Udp Port
Transport is Raet transactions, service kind, tail error checking,
Could include header signing as part of transport reliable delivery serialization of header
Session is session id key exchange for signing. Grouping is Road (like 852 channel)
Presentation is Encrypt Decrypt body Serialize Deserialize Body
Application is body data dictionary

Header signing spans both the Transport and Session layers.

Header
------

JSON Header (Tradeoff some processing speed for extensibility, ease of use, readability)

Body initially JSON but support for "packed" binary body


Packet
------

Header ASCII Safe JSON
Header termination:
Empty line given by double pair of carriage return linefeed
/r/n/r/n
10 13 10 13
ADAD
1010 1101 1010 1101

In json carriage return and newline characters cannot appear in a json encoded
string unless they are escaped with backslash, so the 4 byte combination is illegal in valid
json that does not have multi-byte unicode characters.

These means the header must be ascii safe  so no multibyte utf-8 strings
allowed in header.

Following Header Terminator is variable length signature block. This is binary
and the length is provided in the header.

Following the signature block is the packet body or data.
This may either be JSON or packed binary.
The format is given in the json header

Finally is an optional tail block for error checking or encryption details


Header Fields
-------------

In UDP header

sh = source host
sp = source port
dh = destination host
dp = destination port


In RAET Header

hk = header kind
hl = header length

vn = version number

sd = Source Device ID
dd = Destination Device ID
cf = Corresponder Flag
mf = Multicast Flag

si = Session ID
ti = Transaction ID

sk = Service Kind
pk = Packet Kind
bf = Burst Flag  (Send all Segments or Ordered packets without interleaved acks)

oi = Order Index
dt = DateTime Stamp

sn = Segment Number
sc = Segment Count

pf = Pending Segment Flag
af = All Flag   (Resent all Segments not just one)

nk = Auth header kind
nl = Auth header length

bk = body kind
bl = body length

tk = tail kind
tl = tail length

fg = flags  packed (Flags) Default '00' hex string
                 2 byte Hex string with bits (0, 0, af, pf, 0, bf, mf, cf)
                 Zeros are TBD flags


Session Bootstrap
-----------------

Minion sends packet with SID of Zero with public key of minions Public Private Key pair
Master acks packet with SID of Zero to let minion know it received the request

Some time later Master sends packet with SID of zero that accepts the Minion

Minion


Session
-------
Session is important for security. Want one session opened and then multiple
transactions within session.

Session ID
SID
sid

GUID hash to guarantee uniqueness since no guarantee of nonvolatile storage
or require file storage to keep last session ID used.

Service Types or Modular Services
---------------------------------
Four Service Types

A) One or more maybe (unacknowledged repeat) maybe means no guarantee

B) Exactly one at most  (ack with retries) (duplicate detection idempotent)
        at most means fixed number of retries has finite probability of failing
        B1) finite retries
        B2) infinite retries with exponential back-off up to a maximum delay

C) Exactly one of sequence at most (sequence numbered)
        Receiver requests retry of missing packet with same B1 or B2 retry type

D) End to End (Application layer Request Response)
      This is two B sub transactions

Initially unicast messaging
Eventually support for Multicast

The use case for C) is to fragment large packets as once a UDP packet
exceeds the frame size its reliability goes way down
So its more reliable to fragment large packets.


Better approach might be to have more modularity.
Services Levels

    1) Maybe one or more
        A) Fire and forget
            no transaction either side
        B) Repeat, no ack, no dupdet
            repeat counter send side,
            no transaction on receive side
        C) Repeat, no Ack, dupdet
            repeat counter send side,
            dup detection transaction receive side
    2) More or Less Once
        A) retry finite, ack no dupdet
            retry timer send side, finite number of retires
            ack receive side no dupdet
    3) At most Once
        A) retry finite, ack, dupdet
            retry timer send side, finite number of retires
            ack receive side dupdet
    4) Exactly once
        A) ack retry
            retry timer send side,
            ack and duplicate detection receive side
            Infinite retries with exponential backoff
    5) Sequential sequence number
            A) reorder escrow
            B) Segmented packets
    6) request response to application layer



Service Features

1) repeats
2) ack retry transaction id
3) sequence number duplicate detection  out of order detection sequencing
4) rep-req


Always include transaction id since multiple transactions on same port
So get duplicate detection for free if keep transaction alive but if use


A) Maybe one or more
B1) At Least One
B2) Exactly One
C) One of sequence
D) End to End

A) Sender creates transaction id for number of repeats but receiver does not
keep transaction alive

B1) Sender creates transaction id  keeps it for retries.
Receiver keeps it to send ack then kills so retry could be duplicate not detected

B2) Sender creates transaction id keeps for retries
Receiver keeps tid for acks on any retires so no duplicates.

C) Sender creates TID and Sequence Number.
Receiver checks for out of order sequence and can request retry.

D) Application layer sends response. So question is do we keep transaction open
or have response be new transaction. No because then we need a rep-req ID so
might as well use the same transaction id. Just keep alive until get response.

Little advantage to B1 vs B2 not having duplicates.

So 4 service types

A) Maybe one or more (unacknowledged repeat)

B) Exactly One (At most one)  (ack with retry) (duplicate detection idempotent)

C) One of Sequence (sequence numbered)

D) End to End


Also multicast or unicast


Modular Transaction Table

Sender Side:
   Transaction ID plus transaction source sender or receiver generated transaction id
   Repeat Counter
   Retry Timer Retry Counter (finite retries)
   Redo Timer (infinite redos with exponential backoff)
   Sequence number without acks (look for resend requests)
   Sequence with ack (wait for ack before sending next in sequence)
   Segmentation

Receiver Side:
   Nothing just accept packet
   Acknowledge (can delete transaction after acknowledge)
   No duplicate detection
   Transaction timeout (keep transaction until timeout)
   Duplicate detection save transaction id duplicate detection timeout
   Request resend of missing packet in sequence
   Sequence reordering with escrow timeout wait escrow before requesting resend
   Unsegmentation (request resends of missing segment)
