__version_info__ = (0, 8, 4)
__version__ = '.'.join(map(str, __version_info__))

# If we can get a version from Git use that instead, otherwise carry on
try:
    import subprocess
    from salt.utils import which

    git = which('git')
    if git:
        p = subprocess.Popen([git, 'describe'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
        out, err = p.communicate()
        if out:
            __version__ = '{0}'.format(out.strip().lstrip('v'))
            __version_info__ = tuple(__version__.split('-', 1)[0].split('.'))
except Exception:
    pass

if __name__ == '__main__':
    print(__version__)
