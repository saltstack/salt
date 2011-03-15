'''
Work with vitual machines managed by libvirt
'''
# Import Python Libs
import os
import sub_process
import libvirt
import subprocess
import StringIO
from xml.dom import minidom
# Import libvirt
import libvirt

VIRT_STATE_NAME_MAP = {
   0 : "running",
   1 : "running",
   2 : "running",
   3 : "paused",
   4 : "shutdown",
   5 : "shutdown",
   6 : "crashed"
}
