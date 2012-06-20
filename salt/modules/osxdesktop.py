'''
Mac OS X implementations of various commands in the "desktop" interface
'''


def __virtual__():
    if __grains__['os'] == 'MacOS':
        return 'desktop'


def get_output_volume():
    '''
    Get the output volume (range 0 to 100)

    CLI Example::

        salt '*' desktop.get_output_volume
    '''
    cmd = 'osascript -e "get output volume of (get volume settings)"'

    return __salt__['cmd.run'](cmd)


def set_output_volume(volume):
    '''
    Set the volume of sound (range 0 to 100)

    CLI Example::

        salt '*' desktop.set_output_volume <volume>
    '''
    cmd = 'osascript -e "set volume output volume {0}"'.format(volume)

    __salt__['cmd.run'](cmd)

    return get_output_volume()


def screensaver():
    '''
    Launch the screensaver

    CLI Example::

        salt '*' desktop.screensaver
    '''
    cmd = 'open /System/Library/Frameworks/ScreenSaver.framework/Versions/A/Resources/ScreenSaverEngine.app'

    return __salt__['cmd.run'](cmd)


def lock():
    '''
    Lock the desktop session

    CLI Example::

        salt '*' desktop.lock
    '''
    cmd = '/System/Library/CoreServices/Menu\ Extras/User.menu/Contents/Resources/CGSession -suspend'

    return __salt__['cmd.run'](cmd)
