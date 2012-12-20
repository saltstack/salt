============================
Salt Authentication Protocol
============================

The Salt Authentication Protocol (SAP) defines a viable mechanism to create an
authenticated, encrypted communication channel. The SAP is used to create a
general purpose secure communication channel.

Editor: Thomas S Hatch <thatch45@gmail.com>

Licence
=======

Copyright (c) 2011 Thomas S Hatch

This Specification is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the Free
Software Foundation; either version 3 of the License, or (at your option) any
later version.

This Specification is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
details.

You should have received a copy of the GNU General Public License along with
this program; if not, see <http://www.gnu.org/licenses>.

Change Process
==============

This Specification is a free and open standard[2] and is governed by the Digital
Standards Organization's Consensus-Oriented Specification System (COSS)[3].

Language
========

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be
interpreted as described in RFC 2119[1].

Goals
=====

The Salt Authentication Protocol (SAP) defines an authentication system and a
mechanism for sending transport layer encrypted messages.

The goals of SAP are to:
    Define a mechanism for secure authentication which can be utilized by other
    protocols

    Define a message structure which can be managed for clear, pubkey and aes
    encrypted messages

Architecture
============
