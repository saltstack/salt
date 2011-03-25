'''
Some of the utils used by salt
'''
# Import python libs
import os
import sys

def daemonize():
    '''
    Daemonize a process
    '''
    try: 
        pid = os.fork() 
        if pid > 0:
            # exit first parent
            sys.exit(0) 
    except OSError, e: 
        print >> sys.stderr, "fork #1 failed: %d (%s)" % (e.errno, e.strerror)
        sys.exit(1)

    # decouple from parent environment
    os.chdir("/") 
    os.setsid() 
    os.umask(022) 

    # do second fork
    try: 
        pid = os.fork() 
        if pid > 0:
            # print "Daemon PID %d" % pid 
            sys.exit(0) 
    except OSError, e: 
        print >> sys.stderr, "fork #2 failed: %d (%s)" % (e.errno, e.strerror)
        sys.exit(1) 

    dev_null = open('/dev/null','rw') 
    os.dup2(dev_null.fileno(), sys.stdin.fileno()) 
    os.dup2(dev_null.fileno(), sys.stdout.fileno()) 
    os.dup2(dev_null.fileno(), sys.stderr.fileno()) 

def check_root():
    '''
    Most of the salt scripts need to run as root, this function will simply
    verify that root is the user before the application discovers it.
    '''
    if os.getuid():
        print 'Sorry, the salt must run as root, it needs to opperate'\
                + ' in a privileged environment to do what it does.\n' \
                + 'http://xkcd.com/838/'
        sys.exit(1)


