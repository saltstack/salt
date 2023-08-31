==========================
Solaris-specific Behaviour
==========================

Salt is capable of managing Solaris systems, however due to various differences
between the operating systems, there are some things you need to keep in mind.

This document will contain any quirks that apply across Salt or limitations in
some modules.


FQDN/UQDN
=========================
On Solaris platforms the FQDN will not always be properly detected.
If an IPv6 address is configured pythons ```socket.getfqdn()``` fails to return
a FQDN and returns the nodename instead. For a full breakdown see the following
issue on github: #37027

Grains
=========================
Not all grains are available or some have empty or 0 as value. Mostly grains
that are dependent on hardware discovery like:
- num_gpus
- gpus

Also some resolver related grains like:
- domain
- dns:options
- dns:sortlist
