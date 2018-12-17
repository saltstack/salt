# -*- coding: utf-8 -*-
# pylint: skip-file

# This is just the Python 3.7 weakref.finalize implementation

# A. HISTORY OF THE SOFTWARE
# ==========================
#
# Python was created in the early 1990s by Guido van Rossum at Stichting
# Mathematisch Centrum (CWI, see http://www.cwi.nl) in the Netherlands
# as a successor of a language called ABC.  Guido remains Python's
# principal author, although it includes many contributions from others.
#
# In 1995, Guido continued his work on Python at the Corporation for
# National Research Initiatives (CNRI, see http://www.cnri.reston.va.us)
# in Reston, Virginia where he released several versions of the
# software.
#
# In May 2000, Guido and the Python core development team moved to
# BeOpen.com to form the BeOpen PythonLabs team.  In October of the same
# year, the PythonLabs team moved to Digital Creations, which became
# Zope Corporation.  In 2001, the Python Software Foundation (PSF, see
# https://www.python.org/psf/) was formed, a non-profit organization
# created specifically to own Python-related Intellectual Property.
# Zope Corporation was a sponsoring member of the PSF.
#
# All Python releases are Open Source (see http://www.opensource.org for
# the Open Source Definition).  Historically, most, but not all, Python
# releases have also been GPL-compatible; the table below summarizes
# the various releases.
#
#     Release         Derived     Year        Owner       GPL-
#                     from                                compatible? (1)
#
#     0.9.0 thru 1.2              1991-1995   CWI         yes
#     1.3 thru 1.5.2  1.2         1995-1999   CNRI        yes
#     1.6             1.5.2       2000        CNRI        no
#     2.0             1.6         2000        BeOpen.com  no
#     1.6.1           1.6         2001        CNRI        yes (2)
#     2.1             2.0+1.6.1   2001        PSF         no
#     2.0.1           2.0+1.6.1   2001        PSF         yes
#     2.1.1           2.1+2.0.1   2001        PSF         yes
#     2.1.2           2.1.1       2002        PSF         yes
#     2.1.3           2.1.2       2002        PSF         yes
#     2.2 and above   2.1.1       2001-now    PSF         yes
#
# Footnotes:
#
# (1) GPL-compatible doesn't mean that we're distributing Python under
#     the GPL.  All Python licenses, unlike the GPL, let you distribute
#     a modified version without making your changes open source.  The
#     GPL-compatible licenses make it possible to combine Python with
#     other software that is released under the GPL; the others don't.
#
# (2) According to Richard Stallman, 1.6.1 is not GPL-compatible,
#     because its license has a choice of law clause.  According to
#     CNRI, however, Stallman's lawyer has told CNRI's lawyer that 1.6.1
#     is "not incompatible" with the GPL.
#
# Thanks to the many outside volunteers who have worked under Guido's
# direction to make these releases possible.
#
#
# B. TERMS AND CONDITIONS FOR ACCESSING OR OTHERWISE USING PYTHON
# ===============================================================
#
# PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2
# --------------------------------------------
#
# 1. This LICENSE AGREEMENT is between the Python Software Foundation
# ("PSF"), and the Individual or Organization ("Licensee") accessing and
# otherwise using this software ("Python") in source or binary form and
# its associated documentation.
#
# 2. Subject to the terms and conditions of this License Agreement, PSF hereby
# grants Licensee a nonexclusive, royalty-free, world-wide license to reproduce,
# analyze, test, perform and/or display publicly, prepare derivative works,
# distribute, and otherwise use Python alone or in any derivative version,
# provided, however, that PSF's License Agreement and PSF's notice of copyright,
# i.e., "Copyright (c) 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010,
# 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018 Python Software Foundation; All
# Rights Reserved" are retained in Python alone or in any derivative version
# prepared by Licensee.
#
# 3. In the event Licensee prepares a derivative work that is based on
# or incorporates Python or any part thereof, and wants to make
# the derivative work available to others as provided herein, then
# Licensee hereby agrees to include in any such work a brief summary of
# the changes made to Python.
#
# 4. PSF is making Python available to Licensee on an "AS IS"
# basis.  PSF MAKES NO REPRESENTATIONS OR WARRANTIES, EXPRESS OR
# IMPLIED.  BY WAY OF EXAMPLE, BUT NOT LIMITATION, PSF MAKES NO AND
# DISCLAIMS ANY REPRESENTATION OR WARRANTY OF MERCHANTABILITY OR FITNESS
# FOR ANY PARTICULAR PURPOSE OR THAT THE USE OF PYTHON WILL NOT
# INFRINGE ANY THIRD PARTY RIGHTS.
#
# 5. PSF SHALL NOT BE LIABLE TO LICENSEE OR ANY OTHER USERS OF PYTHON
# FOR ANY INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES OR LOSS AS
# A RESULT OF MODIFYING, DISTRIBUTING, OR OTHERWISE USING PYTHON,
# OR ANY DERIVATIVE THEREOF, EVEN IF ADVISED OF THE POSSIBILITY THEREOF.
#
# 6. This License Agreement will automatically terminate upon a material
# breach of its terms and conditions.
#
# 7. Nothing in this License Agreement shall be deemed to create any
# relationship of agency, partnership, or joint venture between PSF and
# Licensee.  This License Agreement does not grant permission to use PSF
# trademarks or trade name in a trademark sense to endorse or promote
# products or services of Licensee, or any third party.
#
# 8. By copying, installing or otherwise using Python, Licensee
# agrees to be bound by the terms and conditions of this License
# Agreement.
#
#
# BEOPEN.COM LICENSE AGREEMENT FOR PYTHON 2.0
# -------------------------------------------
#
# BEOPEN PYTHON OPEN SOURCE LICENSE AGREEMENT VERSION 1
#
# 1. This LICENSE AGREEMENT is between BeOpen.com ("BeOpen"), having an
# office at 160 Saratoga Avenue, Santa Clara, CA 95051, and the
# Individual or Organization ("Licensee") accessing and otherwise using
# this software in source or binary form and its associated
# documentation ("the Software").
#
# 2. Subject to the terms and conditions of this BeOpen Python License
# Agreement, BeOpen hereby grants Licensee a non-exclusive,
# royalty-free, world-wide license to reproduce, analyze, test, perform
# and/or display publicly, prepare derivative works, distribute, and
# otherwise use the Software alone or in any derivative version,
# provided, however, that the BeOpen Python License is retained in the
# Software, alone or in any derivative version prepared by Licensee.
#
# 3. BeOpen is making the Software available to Licensee on an "AS IS"
# basis.  BEOPEN MAKES NO REPRESENTATIONS OR WARRANTIES, EXPRESS OR
# IMPLIED.  BY WAY OF EXAMPLE, BUT NOT LIMITATION, BEOPEN MAKES NO AND
# DISCLAIMS ANY REPRESENTATION OR WARRANTY OF MERCHANTABILITY OR FITNESS
# FOR ANY PARTICULAR PURPOSE OR THAT THE USE OF THE SOFTWARE WILL NOT
# INFRINGE ANY THIRD PARTY RIGHTS.
#
# 4. BEOPEN SHALL NOT BE LIABLE TO LICENSEE OR ANY OTHER USERS OF THE
# SOFTWARE FOR ANY INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES OR LOSS
# AS A RESULT OF USING, MODIFYING OR DISTRIBUTING THE SOFTWARE, OR ANY
# DERIVATIVE THEREOF, EVEN IF ADVISED OF THE POSSIBILITY THEREOF.
#
# 5. This License Agreement will automatically terminate upon a material
# breach of its terms and conditions.
#
# 6. This License Agreement shall be governed by and interpreted in all
# respects by the law of the State of California, excluding conflict of
# law provisions.  Nothing in this License Agreement shall be deemed to
# create any relationship of agency, partnership, or joint venture
# between BeOpen and Licensee.  This License Agreement does not grant
# permission to use BeOpen trademarks or trade names in a trademark
# sense to endorse or promote products or services of Licensee, or any
# third party.  As an exception, the "BeOpen Python" logos available at
# http://www.pythonlabs.com/logos.html may be used according to the
# permissions granted on that web page.
#
# 7. By copying, installing or otherwise using the software, Licensee
# agrees to be bound by the terms and conditions of this License
# Agreement.
#
#
# CNRI LICENSE AGREEMENT FOR PYTHON 1.6.1
# ---------------------------------------
#
# 1. This LICENSE AGREEMENT is between the Corporation for National
# Research Initiatives, having an office at 1895 Preston White Drive,
# Reston, VA 20191 ("CNRI"), and the Individual or Organization
# ("Licensee") accessing and otherwise using Python 1.6.1 software in
# source or binary form and its associated documentation.
#
# 2. Subject to the terms and conditions of this License Agreement, CNRI
# hereby grants Licensee a nonexclusive, royalty-free, world-wide
# license to reproduce, analyze, test, perform and/or display publicly,
# prepare derivative works, distribute, and otherwise use Python 1.6.1
# alone or in any derivative version, provided, however, that CNRI's
# License Agreement and CNRI's notice of copyright, i.e., "Copyright (c)
# 1995-2001 Corporation for National Research Initiatives; All Rights
# Reserved" are retained in Python 1.6.1 alone or in any derivative
# version prepared by Licensee.  Alternately, in lieu of CNRI's License
# Agreement, Licensee may substitute the following text (omitting the
# quotes): "Python 1.6.1 is made available subject to the terms and
# conditions in CNRI's License Agreement.  This Agreement together with
# Python 1.6.1 may be located on the Internet using the following
# unique, persistent identifier (known as a handle): 1895.22/1013.  This
# Agreement may also be obtained from a proxy server on the Internet
# using the following URL: http://hdl.handle.net/1895.22/1013".
#
# 3. In the event Licensee prepares a derivative work that is based on
# or incorporates Python 1.6.1 or any part thereof, and wants to make
# the derivative work available to others as provided herein, then
# Licensee hereby agrees to include in any such work a brief summary of
# the changes made to Python 1.6.1.
#
# 4. CNRI is making Python 1.6.1 available to Licensee on an "AS IS"
# basis.  CNRI MAKES NO REPRESENTATIONS OR WARRANTIES, EXPRESS OR
# IMPLIED.  BY WAY OF EXAMPLE, BUT NOT LIMITATION, CNRI MAKES NO AND
# DISCLAIMS ANY REPRESENTATION OR WARRANTY OF MERCHANTABILITY OR FITNESS
# FOR ANY PARTICULAR PURPOSE OR THAT THE USE OF PYTHON 1.6.1 WILL NOT
# INFRINGE ANY THIRD PARTY RIGHTS.
#
# 5. CNRI SHALL NOT BE LIABLE TO LICENSEE OR ANY OTHER USERS OF PYTHON
# 1.6.1 FOR ANY INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES OR LOSS AS
# A RESULT OF MODIFYING, DISTRIBUTING, OR OTHERWISE USING PYTHON 1.6.1,
# OR ANY DERIVATIVE THEREOF, EVEN IF ADVISED OF THE POSSIBILITY THEREOF.
#
# 6. This License Agreement will automatically terminate upon a material
# breach of its terms and conditions.
#
# 7. This License Agreement shall be governed by the federal
# intellectual property law of the United States, including without
# limitation the federal copyright law, and, to the extent such
# U.S. federal law does not apply, by the law of the Commonwealth of
# Virginia, excluding Virginia's conflict of law provisions.
# Notwithstanding the foregoing, with regard to derivative works based
# on Python 1.6.1 that incorporate non-separable material that was
# previously distributed under the GNU General Public License (GPL), the
# law of the Commonwealth of Virginia shall govern this License
# Agreement only as to issues arising under or with respect to
# Paragraphs 4, 5, and 7 of this License Agreement.  Nothing in this
# License Agreement shall be deemed to create any relationship of
# agency, partnership, or joint venture between CNRI and Licensee.  This
# License Agreement does not grant permission to use CNRI trademarks or
# trade name in a trademark sense to endorse or promote products or
# services of Licensee, or any third party.
#
# 8. By clicking on the "ACCEPT" button where indicated, or by copying,
# installing or otherwise using Python 1.6.1, Licensee agrees to be
# bound by the terms and conditions of this License Agreement.
#
#         ACCEPT
#
#
# CWI LICENSE AGREEMENT FOR PYTHON 0.9.0 THROUGH 1.2
# --------------------------------------------------
#
# Copyright (c) 1991 - 1995, Stichting Mathematisch Centrum Amsterdam,
# The Netherlands.  All rights reserved.
#
# Permission to use, copy, modify, and distribute this software and its
# documentation for any purpose and without fee is hereby granted,
# provided that the above copyright notice appear in all copies and that
# both that copyright notice and this permission notice appear in
# supporting documentation, and that the name of Stichting Mathematisch
# Centrum or CWI not be used in advertising or publicity pertaining to
# distribution of the software without specific, written prior
# permission.
#
# STICHTING MATHEMATISCH CENTRUM DISCLAIMS ALL WARRANTIES WITH REGARD TO
# THIS SOFTWARE, INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
# FITNESS, IN NO EVENT SHALL STICHTING MATHEMATISCH CENTRUM BE LIABLE
# FOR ANY SPECIAL, INDIRECT OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT
# OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

# Import Python Libs
import sys
import itertools
from weakref import ref


class finalize:
    """Class for finalization of weakrefable objects

    finalize(obj, func, *args, **kwargs) returns a callable finalizer
    object which will be called when obj is garbage collected. The
    first time the finalizer is called it evaluates func(*arg, **kwargs)
    and returns the result. After this the finalizer is dead, and
    calling it just returns None.

    When the program exits any remaining finalizers for which the
    atexit attribute is true will be run in reverse order of creation.
    By default atexit is true.
    """

    # Finalizer objects don't have any state of their own.  They are
    # just used as keys to lookup _Info objects in the registry.  This
    # ensures that they cannot be part of a ref-cycle.

    __slots__ = ()
    _registry = {}
    _shutdown = False
    _index_iter = itertools.count()
    _dirty = False
    _registered_with_atexit = False

    class _Info:
        __slots__ = ("weakref", "func", "args", "kwargs", "atexit", "index")

    def __init__(self, obj, func, *args, **kwargs):
        if not self._registered_with_atexit:
            # We may register the exit function more than once because
            # of a thread race, but that is harmless
            import atexit
            atexit.register(self._exitfunc)
            finalize._registered_with_atexit = True
        info = self._Info()
        info.weakref = ref(obj, self)
        info.func = func
        info.args = args
        info.kwargs = kwargs or None
        info.atexit = True
        info.index = next(self._index_iter)
        self._registry[self] = info
        finalize._dirty = True

    def __call__(self, _=None):
        """If alive then mark as dead and return func(*args, **kwargs);
        otherwise return None"""
        info = self._registry.pop(self, None)
        if info and not self._shutdown:
            return info.func(*info.args, **(info.kwargs or {}))

    def detach(self):
        """If alive then mark as dead and return (obj, func, args, kwargs);
        otherwise return None"""
        info = self._registry.get(self)
        obj = info and info.weakref()
        if obj is not None and self._registry.pop(self, None):
            return (obj, info.func, info.args, info.kwargs or {})

    def peek(self):
        """If alive then return (obj, func, args, kwargs);
        otherwise return None"""
        info = self._registry.get(self)
        obj = info and info.weakref()
        if obj is not None:
            return (obj, info.func, info.args, info.kwargs or {})

    @property
    def alive(self):
        """Whether finalizer is alive"""
        return self in self._registry

    @property
    def atexit(self):
        """Whether finalizer should be called at exit"""
        info = self._registry.get(self)
        return bool(info) and info.atexit

    @atexit.setter
    def atexit(self, value):
        info = self._registry.get(self)
        if info:
            info.atexit = bool(value)

    def __repr__(self):
        info = self._registry.get(self)
        obj = info and info.weakref()
        if obj is None:
            return '<%s object at %#x; dead>' % (type(self).__name__, id(self))
        else:
            return '<%s object at %#x; for %r at %#x>' % \
                (type(self).__name__, id(self), type(obj).__name__, id(obj))

    @classmethod
    def _select_for_exit(cls):
        # Return live finalizers marked for exit, oldest first
        L = [(f,i) for (f,i) in cls._registry.items() if i.atexit]
        L.sort(key=lambda item:item[1].index)
        return [f for (f,i) in L]

    @classmethod
    def _exitfunc(cls):
        # At shutdown invoke finalizers for which atexit is true.
        # This is called once all other non-daemonic threads have been
        # joined.
        reenable_gc = False
        try:
            if cls._registry:
                import gc
                if gc.isenabled():
                    reenable_gc = True
                    gc.disable()
                pending = None
                while True:
                    if pending is None or finalize._dirty:
                        pending = cls._select_for_exit()
                        finalize._dirty = False
                    if not pending:
                        break
                    f = pending.pop()
                    try:
                        # gc is disabled, so (assuming no daemonic
                        # threads) the following is the only line in
                        # this function which might trigger creation
                        # of a new finalizer
                        f()
                    except Exception:
                        sys.excepthook(*sys.exc_info())
                    assert f not in cls._registry
        finally:
            # prevent any more finalizers from executing during shutdown
            finalize._shutdown = True
            if reenable_gc:
                gc.enable()
