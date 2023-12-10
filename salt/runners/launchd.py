"""
Manage launchd plist files
"""

import os
import sys


def write_launchd_plist(program):
    """
    Write a launchd plist for managing salt-master or salt-minion

    CLI Example:

    .. code-block:: bash

        salt-run launchd.write_launchd_plist salt-master
    """
    plist_sample_text = """
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>org.saltstack.{program}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>ProgramArguments</key>
    <array>
        <string>{script}</string>
    </array>
    <key>SoftResourceLimits</key>
    <dict>
        <key>NumberOfFiles</key>
        <integer>100000</integer>
    </dict>
    <key>HardResourceLimits</key>
    <dict>
        <key>NumberOfFiles</key>
        <integer>100000</integer>
    </dict>
  </dict>
</plist>
    """.strip()

    supported_programs = ["salt-master", "salt-minion"]

    if program not in supported_programs:
        sys.stderr.write("Supported programs: '{}'\n".format(supported_programs))
        sys.exit(-1)

        return plist_sample_text.format(
            program=program,
            python=sys.executable,
            script=os.path.join(os.path.dirname(sys.executable), program),
        )
