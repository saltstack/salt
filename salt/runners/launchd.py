import os
import sys

def write_launchd_plist(program):
    '''
    Write a launchd plist for managing salt-master or salt-minion
    '''
    plist_sample_text="""
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>org.saltstack.{program}</string>

    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>{script}</string>
    </array>

    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
    """.strip()

    supported_programs = ['salt-master', 'salt-minion']

    if program not in supported_programs:
        sys.stderr.write("Supported programs: %r\n" % supported_programs)
        sys.exit(-1)
    
    sys.stdout.write(
        plist_sample_text.format(
            program=program,
            python=sys.executable,
            script=os.path.join(os.path.dirname(sys.executable), program)
        )
    )
