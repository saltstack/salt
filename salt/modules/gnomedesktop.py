# -*- coding: utf-8 -*-
'''
GNOME implementations 
'''

try:
    from gi.repository import Gio,GLib
    HAS_GLIB = True
except:
    HAS_GLIB = False

import logging
import psutil
import pwd
import os
import subprocess
import sys
import time

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'gnome'

def __virtual__():
    '''
    Only load if the Gio and Glib modules are available
    '''
    if HAS_GLIB:
        return __virtualname__
    return False

class _GSettings:

    def __init__(self, user, schema, key, ftype):
        self.SCHEMA = schema
        self.KEY = key
        self.FTYPE = ftype

        if not user:
            self.USER = os.getenv("USER")
        else:
            self.USER = user

        self.UID = None
        self.HOME = None

    def _findUID(self, user):
        return pwd.getpwnam(user).pw_uid

    def _switchUser(self, uid, user, dbusAddress):

        # Change child process to run as user
        os.setuid(uid)

        # Set ENV variables needed for DBUS connections
        os.putenv('HOME',pwd.getpwnam(user).pw_dir)
        os.putenv('XDG_RUNTIME_DIR',"/run/user/%d" % (uid))
        os.putenv('DBUS_SESSION_BUS_ADDRESS', dbusAddress)
        #os.putenv('DISPLAY',":0")

    def _findDBUS(self, user):

        HOME = pwd.getpwnam(user).pw_dir
        session_file = None

        # Check User's home dir first, then /root
        for dir in ["%s/.dbus/session-bus" % (HOME), "/root/.dbus/session-bus"]:

            # Path doesn't exist, next
            if not os.path.exists(dir):
                continue

            # If there are no session files, next
            sessions = os.listdir(dir)
            if not len(sessions):
                continue
            session_file = "%s/%s" % (dir, sessions[0])

        # DBUS isn't running, return false
        if not session_file:
            log.debug("No DBUS available")
            return False
        
        ENVIRON = {}
        content = open(session_file).readlines()
        for line in content:
            if not line[0] == '#':
                key,value = line.split("=", 1)
                ENVIRON[key] = value
	
        return ENVIRON['DBUS_SESSION_BUS_ADDRESS']

    def _get(self):

        user = self.USER
        uid = self._findUID(user)
        dbusAddress = self._findDBUS(user)
        if not dbusAddress:
            msg = "Error: DBUS not accessible"
            log.error(msg)
            return msg

        # Fork and open a pipe
        r, w = os.pipe()
        pid = os.fork()

        if pid:
            # parent
            os.close(w) # use os.close() to close a file descriptor
            r = os.fdopen(r)
            result = r.read()
            os.waitpid(pid, 0)

        else:
            # child
            os.close(r)
            w = os.fdopen(w, 'w')

            # Change child process to run as user
            log.debug("switching to %d" % (uid))
            self._switchUser(uid, user, dbusAddress)

            gsettings = Gio.Settings.new(self.SCHEMA)
            if self.FTYPE == 'boolean':
                result =  gsettings.get_boolean(self.KEY)
            elif self.FTYPE == 'variant':
                result = gsettings.get_value(self.KEY).get_uint32()
            elif self.FTYPE == 'int':
                result = gsettings.get_int(self.KEY)
            elif self.FTYPE == 'string':
                result = gsettings.get_string(self.KEY)
            else:
                result = False

            w.write(str(result))
            w.close()
            os._exit(os.EX_OK)

        return result

    def _set(self, value):
        user = self.USER
        uid = self._findUID(user)
        dbusAddress = self._findDBUS(user)

        if not dbusAddress:
            msg = "Error: DBUS not accessible"
            log.error(msg)
            return msg

        # Fork and open a pipe
        r, w = os.pipe()
        pid = os.fork()

        if pid:
            # parent
            os.close(w) # use os.close() to close a file descriptor
            r = os.fdopen(r)
            result = r.read()
            os.waitpid(pid, 0)

        else:
            # child
            os.close(r)
            w = os.fdopen(w, 'w')

            # Change child process to run as user
            log.debug("switching to %d" % (uid))
            self._switchUser(uid, user, dbusAddress)

            gsettings = Gio.Settings.new(self.SCHEMA)

            if self.FTYPE == 'boolean':
                if value == True:
                    result = gsettings.set_boolean(self.KEY, True)
                else:
                    result = gsettings.set_boolean(self.KEY, False)
            elif self.FTYPE == 'variant':
                result = gsettings.set_value(self.KEY,GLib.Variant.new_uint32(value))
            elif self.FTYPE == 'int':
                result = gsettings.set_int(self.KEY,value)
            elif self.FTYPE == 'string':
                result = gsettings.set_string(self.KEY, value)
            else:
                result = False

            gsettings.sync()

            w.write(str(result))
            w.close()
            os._exit(os.EX_OK)

        return result

def ping(**kwargs):
    '''
    A test to ensure the GNOME module is loaded

    CLI Example:

    .. code-block:: bash

        salt '*' gnome.ping user=<username>

    '''
    return True

def getIdleDelay(**kwargs):
    '''
    Return the current idle delay setting in seconds

    CLI Example:

    .. code-block:: bash

        salt '*' gnome.getIdleDelay user=<username>

    '''

    _gsession = _GSettings(user = user, schema = 'org.gnome.desktop.session', key = 'idle-delay', ftype = 'variant')
    return _gsession._get()

def setIdleDelay(delaySeconds, **kwargs):
    '''
    Set the current idle delay setting in seconds

    CLI Example:

    .. code-block:: bash

        salt '*' gnome.setIdleDelay <seconds> user=<username>

    '''

    _gsession = _GSettings(user = user, schema = 'org.gnome.desktop.session', key = 'idle-delay', ftype = 'variant')
    return _gsession._set(delaySeconds)

def getClockFormat(**kwargs):
    '''
    Return the current clock format, either 12h or 24h format.

    CLI Example:

    .. code-block:: bash

        salt '*' gnome.getClockFormat user=<username>

    '''

    _gsession = _GSettings(user = user, schema = 'org.gnome.desktop.interface', key = 'clock-format', ftype = 'string')
    return _gsession._get()

def setClockFormat(clockFormat, **kwargs):
    '''
    Set the clock format, either 12h or 24h format. 

    CLI Example:

    .. code-block:: bash

        salt '*' gnome.setClockFormat <12h|24h> user=<username>

    '''

    if clockFormat != "12h" and clockFormat != "24h":
        return False
    _gsession = _GSettings(user = user, schema = 'org.gnome.desktop.interface', key = 'clock-format', ftype = 'string')
    return _gsession._set(clockFormat)

def getClockShowDate(**kwargs):
    '''
    Return the current setting, if the date is shown in the clock

    CLI Example:

    .. code-block:: bash

        salt '*' gnome.getClockShowDate user=<username>

    '''

    _gsession = _GSettings(user = user, schema = 'org.gnome.desktop.interface', key = 'clock-show-date', ftype = 'boolean')
    return _gsession._get()

def setClockShowDate(kvalue, **kwargs):
    '''
    Set whether the date is visable in the clock

    CLI Example:

    .. code-block:: bash

        salt '*' gnome.setClockShowDate <True|False> user=<username>

    '''

    if kvalue != True and kvalue != False:
        return False
    _gsession = _GSettings(user = user, schema = 'org.gnome.desktop.interface', key = 'clock-show-date', ftype = 'boolean')
    return _gsession._set(kvalue)

def getIdleActivation(**kwargs):
    '''
    Get whether the idle activation is enabled

    CLI Example:

    .. code-block:: bash

        salt '*' gnome.getIdleActivation user=<username>

    '''

    _gsession = _GSettings(user = user, schema = 'org.gnome.desktop.screensaver', key = 'idle-activation-enabled', ftype = 'boolean')
    return _gsession._get()

def setIdleActivation(kvalue, **kwargs):
    '''
    Set whether the idle activation is enabled

    CLI Example:

    .. code-block:: bash

        salt '*' gnome.setIdleActivation <True|False> user=<username>

    '''

    if kvalue != True and kvalue != False:
        return False

    _gsession = _GSettings(user = user, schema = 'org.gnome.desktop.screensaver', key = 'idle-activation-enabled', ftype = 'boolean')
    return _gsession._set(kvalue)


def get(schema = None, key = None, user = None, ftype = None, value= None, **kwargs):
    '''
   Get key in a particular GNOME schema

    CLI Example:

    .. code-block:: bash

        salt '*' gnome.get user=<username> schema=org.gnome.desktop.screensaver key=idle-activation-enabled ftype=boolean

    '''

    _gsession = _GSettings(user = user, schema = schema, key = key, ftype = ftype)
    value = _gsession._get()
    return value

def set(schema = None, key = None, user = None, ftype = None, value = None, **kwargs):
    '''
    Set key in a particular GNOME schema

    CLI Example:

    .. code-block:: bash

        salt '*' gnome.set user=<username> schema=org.gnome.desktop.screensaver key=idle-activation-enabled ftype=boolean value=False

    '''

    _gsession = _GSettings(user = user, schema = schema, key = key, ftype = ftype)

    result = _gsession._set(value)
    return result
