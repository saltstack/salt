'''
Contains systemd related help files
'''
# import python libs
import os


def booted(context):
    '''
    Return True if the system was booted with systemd, False otherwise.
    Pass in the loader context "__context__", this function will set the
    systemd.sd_booted key to represent if systemd is running
    '''
    # We can cache this for as long as the minion runs.
    if "systemd.sd_booted" not in context:
        try:
            # This check does the same as sd_booted() from libsystemd-daemon:
            # http://www.freedesktop.org/software/systemd/man/sd_booted.html
            if os.stat('/run/systemd/system'):
                context['systemd.sd_booted'] = True
        except OSError:
            context['systemd.sd_booted'] = False

    return context['systemd.sd_booted']
