# -*- coding: utf-8 -*-
'''
This is a shim that handles checking and updating salt thin and
then invoking thin.

This is not intended to be instantiated as a module, rather it is a
helper script used by salt.client.ssh.Single.  It is here, in a
seperate file, for convenience of development.
'''

import optparse
import hashlib
import tarfile
import shutil
import sys
import os
import stat

THIN_ARCHIVE = 'salt-thin.tgz'

# FIXME - it would be ideal if these could be obtained directly from
#         salt.exitcodes rather than duplicated.
EX_THIN_DEPLOY = 11
EX_THIN_CHECKSUM = 12


OPTIONS = None
ARGS = None


def parse_argv(argv):
    global OPTIONS
    global ARGS

    oparser = optparse.OptionParser(usage="%prog -- [SHIM_OPTIONS] -- [SALT_OPTIONS]")
    oparser.add_option(
        "-c", "--config",
        default='',
        help="YAML configuration for salt thin",
    )
    oparser.add_option(
        "-d", "--delimiter",
        help="Delimeter string (viz. magic string) to indicate beginning of salt output",
    )
    oparser.add_option(
        "-s", "--saltdir",
        help="Directory where salt thin is or will be installed.",
    )
    oparser.add_option(
        "--sum", "--checksum",
        dest="checksum",
        help="Salt thin checksum",
    )
    oparser.add_option(
        "--hashfunc",
        default='sha1',
        help="Hash function for computing checksum",
    )
    oparser.add_option(
        "-v", "--version",
        help="Salt thin version to be deployed/verified",
    )

    if argv and '--' not in argv:
        oparser.error('A "--" argument must be the initial argument indicating the start of options to this script')

    (OPTIONS, ARGS) = oparser.parse_args(argv[argv.index('--')+1:])

    for option in (
            'delimiter',
            'saltdir',
            'checksum',
            'version',
    ):
        if getattr(OPTIONS, option, None):
            continue
        oparser.error('Option "--{0}" is required.'.format(option))


def need_deployment():
    if os.path.exists(OPTIONS.saltdir):
        shutil.rmtree(OPTIONS.saltdir)
    old_umask = os.umask(0077)
    os.makedirs(OPTIONS.saltdir)
    os.umask(old_umask)
    # If SUDOing then also give the super user group write permissions
    sudo_gid = os.environ.get('SUDO_GID')
    if sudo_gid:
        os.chown(OPTIONS.saltdir, -1, int(sudo_gid))
        st = os.stat(OPTIONS.saltdir)
        os.chmod(OPTIONS.saltdir, st.st_mode | stat.S_IWGRP | stat.S_IRGRP | stat.S_IXGRP)

    # Delimeter emitted on stdout *only* to indicate shim message to master.
    sys.stdout.write("{0}\ndeploy\n".format(OPTIONS.delimiter))
    sys.exit(EX_THIN_DEPLOY)


# Adapted from salt.utils.get_hash()
def get_hash(path, form='md5', chunk_size=4096):
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
    tfile = tarfile.TarFile.gzopen(thin_path)
    tfile.extractall(path=OPTIONS.saltdir)
    tfile.close()
    os.unlink(thin_path)


def main(argv):
    parse_argv(argv)

    thin_path = os.path.join(OPTIONS.saltdir, THIN_ARCHIVE)
    if os.path.exists(thin_path):
        if OPTIONS.checksum != get_hash(thin_path, OPTIONS.hashfunc):
            os.unlink(thin_path)
            sys.stderr.write('WARNING: checksum mismatch for "{0}"\n'.format(thin_path))
            sys.exit(EX_THIN_CHECKSUM)
        unpack_thin(thin_path)
        # Salt thin now is available to use
    else:
        if not os.path.exists(OPTIONS.saltdir):
            need_deployment()

        if not os.path.isdir(OPTIONS.saltdir):
            sys.stderr.write('ERROR: salt path "{0}" exists but is not a directory\n'.format(OPTIONS.saltdir))
            sys.exit(os.EX_CANTCREAT)

        version_path = os.path.join(OPTIONS.saltdir, 'version')
        if not os.path.exists(version_path) or not os.path.isfile(version_path):
            sys.stderr.write('WARNING: Unable to locate current thin version.\n')
            need_deployment()
        with open(version_path, 'r') as vpo:
            cur_version = vpo.readline().strip()
        if cur_version != OPTIONS.version:
            sys.stderr.write('WARNING: current thin version is not up-to-date.\n')
            need_deployment()
        # Salt thin exists and is up-to-date - fall through and use it

    salt_call_path = os.path.join(OPTIONS.saltdir, 'salt-call')
    if not os.path.isfile(salt_call_path):
        sys.stderr.write('ERROR: thin is missing "{0}"\n'.format(salt_call_path))
        sys.exit(os.EX_SOFTWARE)

    with open(os.path.join(OPTIONS.saltdir, 'minion'), 'w') as config:
        config.write(OPTIONS.config + '\n')

    #Fix parameter passing issue
    if len(ARGS) == 1:
        argv_prepared = ARGS[0].split()
    else:
        argv_prepared = ARGS

    salt_argv = [
        sys.executable,
        salt_call_path,
        '--local',
        '--out', 'json',
        '-l', 'quiet',
        '-c', OPTIONS.saltdir,
        '--',
    ] + argv_prepared

    sys.stderr.write('SALT_ARGV: {0}\n'.format(salt_argv))

    # Only emit the delimiter on *both* stdout and stderr when completely successful.
    # Yes, the flush() is necessary.
    sys.stdout.write(OPTIONS.delimiter + '\n')
    sys.stdout.flush()
    sys.stderr.write(OPTIONS.delimiter + '\n')
    sys.stderr.flush()
    os.execv(sys.executable, salt_argv)

if __name__ == "__main__":
    sys.exit(main(sys.argv))
