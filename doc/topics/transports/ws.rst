===================
Websocket Transport
===================

The Websocket transport is an implementation of Salt's transport using the websocket protocol.
The Websocket transport is enabled by changing the :conf_minion:`transport` setting
to ``ws`` on each Salt minion and Salt master.

TLS Support
===========

The Websocket transport supports full encryption and verification using both server
and client certificates. See :doc:`ssl` for more details.

Publish Server and Client
=========================
The publish server and client are implemented using aiohttp.

Request Server and Client
=========================
The request server and client are implemented using aiohttp.
