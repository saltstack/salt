"""
PyInstaller runtime hook to patch subprocess.Popen
"""
import logging
import subprocess

from salt.utils.pyinstaller.rthooks._overrides import PyinstallerPopen

log = logging.getLogger(__name__)
# Patch subprocess.Popen when running within a pyinstalled bundled package
subprocess.Popen = PyinstallerPopen

log.debug("Replaced 'subprocess.Popen' with 'PyinstallerTerminal'")
