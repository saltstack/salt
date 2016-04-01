 .. _transports:

==============
Salt Transport
==============

One of fundamental features of Salt is remote execution. Salt has two basic
"channels" for communicating with minions. Each channel requires a
client (minion) and a server (master) implementation to work within Salt. These
pairs of channels will work together to implement the specific message passing
required by the channel interface.


Pub Channel
===========
The pub channel, or publish channel, is how a master sends a job (payload) to a
minion. This is a basic pub/sub paradigm, which has specific targeting semantics.
All data which goes across the publish system should be encrypted such that only
members of the Salt cluster can decrypt the publishes.


Req Channel
===========
The req channel is how the minions send data to the master. This interface is
primarily used for fetching files and returning job returns. The req channels
have two basic interfaces when talking to the master. ``send`` is the basic
method that guarantees the message is encrypted at least so that only minions
attached to the same master can read it-- but no guarantee of minion-master
confidentiality, wheras the ``crypted_transfer_decode_dictentry`` method does
guarantee minion-master confidentiality.


.. toctree::

    zeromq
    tcp
    raet/index
