import logging
import os
import shutil
from salt import exceptions
from salt.states.git import _fail, _neutral_test

log = logging.getLogger(__name__)

def __virtual__():
    '''
    Only load if svn is available
    '''
    if __salt__["cmd.has_exec"]("svn"):
        return "svn"
    return False

def latest(name,
           target=None,
           rev=None,
           user=None,
           username=None,
           force=None,
           externals=True):
    """
    Make sure the repository is cloned to the given directory and is up to date

    target
        Name of the target directory where the checkout will put the working directory

    name
        Address of the name repository as passed to "svn checkout"

    rev : None
        The name revision number to checkout. Enable "force" if the directory already exists.

    user : None
        Name of the user performing repository management operations

    username : None
        The user to access the name repository with. The svn default is the current user

    force : Fasle
        Force svn to checkout into pre-existing directories (deletes contents)

    externals : True
        Checkout externally tracked files.
    """
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    if not target:
        return _fail(ret, '"target option is required')

    svn_cmd = "svn.checkout"
    cwd, basename = os.path.split(target)
    opts = tuple()

    if os.path.exists(target) and not os.path.isdir(target):
        return _fail(ret, "The path, %s, exists and is not a directory." % target)

    try:
        __salt__["svn.info"](".", target, user=user)
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
        out = __salt__[svn_cmd](cwd, basename, user, *opts)
    else:
        out = __salt__[svn_cmd](cwd, name, basename, user, username, *opts)
    ret["comment"] = out
    return ret

def dirty(target,
          user=None,
          ignore_unversioned=False):
    """
    Determine if the working directory has been changed.
    """
    pass
