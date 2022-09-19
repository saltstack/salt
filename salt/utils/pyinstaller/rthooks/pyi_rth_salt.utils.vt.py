"""
PyInstaller runtime hook to patch salt.utils.vt.Terminal
"""
import logging

import salt.utils.vt
from salt.utils.pyinstaller.rthooks._overrides import PyinstallerTerminal

log = logging.getLogger(__name__)
# Patch salt.utils.vt.Terminal when running within a pyinstalled bundled package
salt.utils.vt.Terminal = PyinstallerTerminal

log.debug("Replaced 'salt.utils.vt.Terminal' with 'PyinstallerTerminal'")
