#!/usr/bin/env python

from bbfreeze import Freezer

includes = ["zmq", "zmq.utils.strtypes", "zmq.utils.jsonapi"]
excludes = ["Tkinter", "tcl", "Tkconstants"]

fre = Freezer(distdir="bb_salt", includes=includes, excludes=excludes)
fre.addScript("/usr/bin/salt-minion")
fre.use_compression = 0
fre.include_py = True
fre()
