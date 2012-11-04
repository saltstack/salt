import logging
import os
import shutil
from salt import exceptions

log = logging.getLogger(__name__)

def __virtual__():
    '''
    Only load if svn is available
    '''
    if __salt__["cmd.has_exec"]("svn"):
        return "svn"
    return False

def latest(target,
           remote,
           rev=None,
           user=None,
           username=None,
           force=None,
           externals=True):
    """
    Make sure the repository is cloned to the given directory and is up to date

    target
        Name of the target directory where the checkout will put the working directory
    remote
        Address of the remote repository as passed to "svn checkout"
    rev : None
        The remote revision number to checkout. Enable "force" if the directory already exists.
    user : None
        Name of the user performing repository management operations
    username : None
        The user to access the remote repository with. The svn default is the current user
    force : Fasle
        Force svn to checkout into pre-existing directories (deletes contents)
    externals : True
        Checkout externally tracked files.
    """
    svn_cmd = "svn.checkout"
    cwd, basename = os.path.split(target)
    opts = tuple()

    if os.path.exists(target) and not os.path.isdir(target):
        log.fatal("The path, %s, exists and is not a directory." % target)
        return False

    try:
        __salt["svn.info"](".", target, user=user)
        svn_cmd = "svn.update"
    except exceptions.CommandExecutionError:
        pass

    if rev:
        opts += ("-r", str(rev))

    if force:
        opts += ("--force",)

    if externals is False:
        opts += ("--ignore-externals",)

    if svn_cmd == "svn.update":
        __salt__[svn_cmd](cwd, basename, user=user, username=username, *opts)
    else:
        __salt__[svn_cmd](cwd, remote, basename, user=user, username=username, *opts)
