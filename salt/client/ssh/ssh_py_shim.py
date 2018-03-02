# pylint: disable=no-encoding-in-file,resource-leakage
'''
This is a shim that handles checking and updating salt thin and
then invoking thin.

This is not intended to be instantiated as a module, rather it is a
helper script used by salt.client.ssh.Single.  It is here, in a
separate file, for convenience of development.
'''
from __future__ import absolute_import, print_function

import hashlib
import tarfile
import shutil
import sys
import os
import stat
import subprocess

THIN_ARCHIVE = 'salt-thin.tgz'
EXT_ARCHIVE = 'salt-ext_mods.tgz'

# Keep these in sync with salt/defaults/exitcodes.py
EX_THIN_DEPLOY = 11
EX_THIN_CHECKSUM = 12
EX_MOD_DEPLOY = 13
EX_SCP_NOT_FOUND = 14
EX_CANTCREAT = 73


class OBJ(object):
    '''
    An empty class for holding instance attribute values.
    '''
    pass


OPTIONS = None
ARGS = None
# The below line is where OPTIONS can be redefined with internal options
# (rather than cli arguments) when the shim is bundled by
# client.ssh.Single._cmd_str()
# pylint: disable=block-comment-should-start-with-cardinal-space
#%%OPTS


def get_system_encoding():
    '''
        Get system encoding. Most of this code is a part of salt/__init__.py
    '''
    # This is the most trustworthy source of the system encoding, though, if
    # salt is being imported after being daemonized, this information is lost
    # and reset to None
    encoding = None

    if not sys.platform.startswith('win') and sys.stdin is not None:
        # On linux we can rely on sys.stdin for the encoding since it
        # most commonly matches the filesystem encoding. This however
        # does not apply to windows
        encoding = sys.stdin.encoding

    if not encoding:
        # If the system is properly configured this should return a valid
        # encoding. MS Windows has problems with this and reports the wrong
        # encoding
        import locale
        try:
            encoding = locale.getdefaultlocale()[-1]
        except ValueError:
            # A bad locale setting was most likely found:
            #   https://github.com/saltstack/salt/issues/26063
            pass

        # This is now garbage collectable
        del locale
        if not encoding:
            # This is most likely ascii which is not the best but we were
            # unable to find a better encoding. If this fails, we fall all
            # the way back to ascii
            encoding = sys.getdefaultencoding()
        if not encoding:
            if sys.platform.startswith('darwin'):
                # Mac OS X uses UTF-8
                encoding = 'utf-8'
            elif sys.platform.startswith('win'):
                # Windows uses a configurable encoding; on Windows, Python uses the name "mbcs"
                # to refer to whatever the currently configured encoding is.
                encoding = 'mbcs'
            else:
                # On linux default to ascii as a last resort
                encoding = 'ascii'
    return encoding


def is_windows():
    '''
    Simple function to return if a host is Windows or not
    '''
    return sys.platform.startswith('win')


def need_deployment():
    '''
    Salt thin needs to be deployed - prep the target directory and emit the
    delimeter and exit code that signals a required deployment.
    '''
    if os.path.exists(OPTIONS.saltdir):
        shutil.rmtree(OPTIONS.saltdir)
    old_umask = os.umask(0o077)
    os.makedirs(OPTIONS.saltdir)
    os.umask(old_umask)
    # Verify perms on saltdir
    if not is_windows():
        euid = os.geteuid()
        dstat = os.stat(OPTIONS.saltdir)
        if dstat.st_uid != euid:
            # Attack detected, try again
            need_deployment()
        if dstat.st_mode != 16832:
            # Attack detected
            need_deployment()
        # If SUDOing then also give the super user group write permissions
        sudo_gid = os.environ.get('SUDO_GID')
        if sudo_gid:
            try:
                os.chown(OPTIONS.saltdir, -1, int(sudo_gid))
                stt = os.stat(OPTIONS.saltdir)
                os.chmod(OPTIONS.saltdir, stt.st_mode | stat.S_IWGRP | stat.S_IRGRP | stat.S_IXGRP)
            except OSError:
                sys.stdout.write('\n\nUnable to set permissions on thin directory.\nIf sudo_user is set '
                        'and is not root, be certain the user is in the same group\nas the login user')
                sys.exit(1)

    # Delimiter emitted on stdout *only* to indicate shim message to master.
    sys.stdout.write("{0}\ndeploy\n".format(OPTIONS.delimiter))
    sys.exit(EX_THIN_DEPLOY)


# Adapted from salt.utils.hashutils.get_hash()
def get_hash(path, form='sha1', chunk_size=4096):
    '''
    Generate a hash digest string for a file.
    '''
    try:
        hash_type = getattr(hashlib, form)
    except AttributeError:
        raise ValueError('Invalid hash type: {0}'.format(form))
    with open(path, 'rb') as ifile:
        hash_obj = hash_type()
        # read the file in in chunks, not the entire file
        for chunk in iter(lambda: ifile.read(chunk_size), b''):
            hash_obj.update(chunk)
        return hash_obj.hexdigest()


def unpack_thin(thin_path):
    '''
    Unpack the Salt thin archive.
    '''
    tfile = tarfile.TarFile.gzopen(thin_path)
    old_umask = os.umask(0o077)
    tfile.extractall(path=OPTIONS.saltdir)
    tfile.close()
    os.umask(old_umask)
    try:
        os.unlink(thin_path)
    except OSError:
        pass


def need_ext():
    '''
    Signal that external modules need to be deployed.
    '''
    sys.stdout.write("{0}\next_mods\n".format(OPTIONS.delimiter))
    sys.exit(EX_MOD_DEPLOY)


def unpack_ext(ext_path):
    '''
    Unpack the external modules.
    '''
    modcache = os.path.join(
            OPTIONS.saltdir,
            'running_data',
            'var',
            'cache',
            'salt',
            'minion',
            'extmods')
    tfile = tarfile.TarFile.gzopen(ext_path)
    old_umask = os.umask(0o077)
    tfile.extractall(path=modcache)
    tfile.close()
    os.umask(old_umask)
    os.unlink(ext_path)
    ver_path = os.path.join(modcache, 'ext_version')
    ver_dst = os.path.join(OPTIONS.saltdir, 'ext_version')
    shutil.move(ver_path, ver_dst)


def main(argv):  # pylint: disable=W0613
    '''
    Main program body
    '''
    thin_path = os.path.join(OPTIONS.saltdir, THIN_ARCHIVE)
    if os.path.isfile(thin_path):
        if OPTIONS.checksum != get_hash(thin_path, OPTIONS.hashfunc):
            need_deployment()
        unpack_thin(thin_path)
        # Salt thin now is available to use
    else:
        if not sys.platform.startswith('win'):
            scpstat = subprocess.Popen(['/bin/sh', '-c', 'command -v scp']).wait()
            if scpstat != 0:
                sys.exit(EX_SCP_NOT_FOUND)

        if not os.path.exists(OPTIONS.saltdir):
            need_deployment()

        if not os.path.isdir(OPTIONS.saltdir):
            sys.stderr.write(
                'ERROR: salt path "{0}" exists but is'
                ' not a directory\n'.format(OPTIONS.saltdir)
            )
            sys.exit(EX_CANTCREAT)

        version_path = os.path.normpath(os.path.join(OPTIONS.saltdir, 'version'))
        if not os.path.exists(version_path) or not os.path.isfile(version_path):
            sys.stderr.write(
                'WARNING: Unable to locate current thin '
                ' version: {0}.\n'.format(version_path)
            )
            need_deployment()
        with open(version_path, 'r') as vpo:
            cur_version = vpo.readline().strip()
        if cur_version != OPTIONS.version:
            sys.stderr.write(
                'WARNING: current thin version {0}'
                ' is not up-to-date with {1}.\n'.format(
                    cur_version, OPTIONS.version
                )
            )
            need_deployment()
        # Salt thin exists and is up-to-date - fall through and use it

    salt_call_path = os.path.join(OPTIONS.saltdir, 'salt-call')
    if not os.path.isfile(salt_call_path):
        sys.stderr.write('ERROR: thin is missing "{0}"\n'.format(salt_call_path))
        need_deployment()

    with open(os.path.join(OPTIONS.saltdir, 'minion'), 'w') as config:
        config.write(OPTIONS.config + '\n')
    if OPTIONS.ext_mods:
        ext_path = os.path.join(OPTIONS.saltdir, EXT_ARCHIVE)
        if os.path.exists(ext_path):
            unpack_ext(ext_path)
        else:
            version_path = os.path.join(OPTIONS.saltdir, 'ext_version')
            if not os.path.exists(version_path) or not os.path.isfile(version_path):
                need_ext()
            with open(version_path, 'r') as vpo:
                cur_version = vpo.readline().strip()
            if cur_version != OPTIONS.ext_mods:
                need_ext()
    # Fix parameter passing issue
    if len(ARGS) == 1:
        argv_prepared = ARGS[0].split()
    else:
        argv_prepared = ARGS

    salt_argv = [
        sys.executable,
        salt_call_path,
        '--retcode-passthrough',
        '--local',
        '--metadata',
        '--out', 'json',
        '-l', 'quiet',
        '-c', OPTIONS.saltdir
    ]

    try:
        if argv_prepared[-1].startswith('--no-parse='):
            salt_argv.append(argv_prepared.pop(-1))
    except (IndexError, TypeError):
        pass

    salt_argv.append('--')
    salt_argv.extend(argv_prepared)

    sys.stderr.write('SALT_ARGV: {0}\n'.format(salt_argv))

    # Only emit the delimiter on *both* stdout and stderr when completely successful.
    # Yes, the flush() is necessary.
    sys.stdout.write(OPTIONS.delimiter + '\n')
    sys.stdout.flush()
    if not OPTIONS.tty:
        sys.stderr.write(OPTIONS.delimiter + '\n')
        sys.stderr.flush()
    if OPTIONS.cmd_umask is not None:
        old_umask = os.umask(OPTIONS.cmd_umask)
    if OPTIONS.tty:
        # Returns bytes instead of string on python 3
        stdout, _ = subprocess.Popen(salt_argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
        sys.stdout.write(stdout.decode(encoding=get_system_encoding(), errors="replace"))
        sys.stdout.flush()
        if OPTIONS.wipe:
            shutil.rmtree(OPTIONS.saltdir)
    elif OPTIONS.wipe:
        subprocess.call(salt_argv)
        shutil.rmtree(OPTIONS.saltdir)
    else:
        subprocess.call(salt_argv)
    if OPTIONS.cmd_umask is not None:
        os.umask(old_umask)

if __name__ == '__main__':
    sys.exit(main(sys.argv))
