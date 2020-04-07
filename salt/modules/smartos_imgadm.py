# -*- coding: utf-8 -*-
"""
Module for running imgadm command on SmartOS
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
import logging

# Import Salt libs
import salt.utils.json
import salt.utils.path
import salt.utils.platform

log = logging.getLogger(__name__)

# Function aliases
__func_alias__ = {
    "list_installed": "list",
    "update_installed": "update",
    "import_image": "import",
}

# Define the module's virtual name
__virtualname__ = "imgadm"


def __virtual__():
    """
    Provides imgadm only on SmartOS
    """
    if salt.utils.platform.is_smartos_globalzone() and salt.utils.path.which("imgadm"):
        return __virtualname__
    return (
        False,
        "{0} module can only be loaded on SmartOS compute nodes".format(
            __virtualname__
        ),
    )


def _exit_status(retcode, stderr=None):
    """
    Translate exit status of imgadm
    """
    ret = {
        0: "Successful completion.",
        1: "An error occurred." if not stderr else stderr,
        2: "Usage error.",
        3: "Image not installed.",
    }[retcode]
    return ret


def _parse_image_meta(image=None, detail=False):
    ret = None

    if image and "Error" in image:
        ret = image
    elif image and "manifest" in image and "name" in image["manifest"]:
        name = image["manifest"]["name"]
        version = image["manifest"]["version"]
        os = image["manifest"]["os"]
        description = image["manifest"]["description"]
        published = image["manifest"]["published_at"]
        source = image["source"]
        if image["manifest"]["name"] == "docker-layer":
            # NOTE: skip docker-layer unless it has a docker:repo and docker:tag
            name = None
            docker_repo = None
            docker_tag = None
            for tag in image["manifest"]["tags"]:
                if tag.startswith("docker:tag:") and image["manifest"]["tags"][tag]:
                    docker_tag = tag.split(":")[-1]
                elif tag == "docker:repo":
                    docker_repo = image["manifest"]["tags"][tag]

            if docker_repo and docker_tag:
                name = "{}:{}".format(docker_repo, docker_tag)
                description = "Docker image imported from {repo}:{tag} on {date}.".format(
                    repo=docker_repo, tag=docker_tag, date=published,
                )

        if name and detail:
            ret = {
                "name": name,
                "version": version,
                "os": os,
                "description": description,
                "published": published,
                "source": source,
            }
        elif name:
            ret = "{name}@{version} [{published}]".format(
                name=name, version=version, published=published,
            )
    else:
        log.debug("smartos_image - encountered invalid image payload: {}".format(image))
        ret = {"Error": "This looks like an orphaned image, image payload was invalid."}

    return ret


def _split_docker_uuid(uuid):
    """
    Split a smartos docker uuid into repo and tag
    """
    if uuid:
        uuid = uuid.split(":")
        if len(uuid) == 2:
            tag = uuid[1]
            repo = uuid[0]
            return repo, tag
    return None, None


def _is_uuid(uuid):
    """
    Check if uuid is a valid smartos uuid

    Example: e69a0918-055d-11e5-8912-e3ceb6df4cf8
    """
    if uuid and list((len(x) for x in uuid.split("-"))) == [8, 4, 4, 4, 12]:
        return True
    return False


def _is_docker_uuid(uuid):
    """
    Check if uuid is a valid smartos docker uuid

    Example plexinc/pms-docker:plexpass
    """
    repo, tag = _split_docker_uuid(uuid)
    return not (not repo and not tag)


def version():
    """
    Return imgadm version

    CLI Example:

    .. code-block:: bash

        salt '*' imgadm.version
    """
    ret = {}
    cmd = "imgadm --version"
    res = __salt__["cmd.run"](cmd).splitlines()
    ret = res[0].split()
    return ret[-1]


def docker_to_uuid(uuid):
    """
    Get the image uuid from an imported docker image

    .. versionadded:: 2019.2.0
    """
    if _is_uuid(uuid):
        return uuid
    if _is_docker_uuid(uuid):
        images = list_installed(verbose=True)
        for image_uuid in images:
            if "name" not in images[image_uuid]:
                continue
            if images[image_uuid]["name"] == uuid:
                return image_uuid
    return None


def update_installed(uuid=""):
    """
    Gather info on unknown image(s) (locally installed)

    uuid : string
        optional uuid of image

    CLI Example:

    .. code-block:: bash

        salt '*' imgadm.update [uuid]
    """
    cmd = "imgadm update {0}".format(uuid).rstrip()
    __salt__["cmd.run"](cmd)
    return {}


def avail(search=None, verbose=False):
    """
    Return a list of available images

    search : string
        search keyword
    verbose : boolean (False)
        toggle verbose output

    CLI Example:

    .. code-block:: bash

        salt '*' imgadm.avail [percona]
        salt '*' imgadm.avail verbose=True
    """
    ret = {}
    cmd = "imgadm avail -j"
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    if retcode != 0:
        ret["Error"] = _exit_status(retcode)
        return ret

    for image in salt.utils.json.loads(res["stdout"]):
        if image["manifest"]["disabled"] or not image["manifest"]["public"]:
            continue
        if search and search not in image["manifest"]["name"]:
            # we skip if we are searching but don't have a match
            continue
        uuid = image["manifest"]["uuid"]
        data = _parse_image_meta(image, verbose)
        if data:
            ret[uuid] = data

    return ret


def list_installed(verbose=False):
    """
    Return a list of installed images

    verbose : boolean (False)
        toggle verbose output

    .. versionchanged:: 2019.2.0

        Docker images are now also listed

    CLI Example:

    .. code-block:: bash

        salt '*' imgadm.list
        salt '*' imgadm.list docker=True
        salt '*' imgadm.list verbose=True
    """
    ret = {}
    cmd = "imgadm list -j"
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    if retcode != 0:
        ret["Error"] = _exit_status(retcode)
        return ret

    for image in salt.utils.json.loads(res["stdout"]):
        uuid = image["manifest"]["uuid"]
        data = _parse_image_meta(image, verbose)
        if data:
            ret[uuid] = data

    return ret


def show(uuid):
    """
    Show manifest of a given image

    uuid : string
        uuid of image

    CLI Example:

    .. code-block:: bash

        salt '*' imgadm.show e42f8c84-bbea-11e2-b920-078fab2aab1f
        salt '*' imgadm.show plexinc/pms-docker:plexpass
    """
    ret = {}

    if _is_uuid(uuid) or _is_docker_uuid(uuid):
        cmd = "imgadm show {0}".format(uuid)
        res = __salt__["cmd.run_all"](cmd, python_shell=False)
        retcode = res["retcode"]
        if retcode != 0:
            ret["Error"] = _exit_status(retcode, res["stderr"])
        else:
            ret = salt.utils.json.loads(res["stdout"])
    else:
        ret["Error"] = "{} is not a valid uuid.".format(uuid)

    return ret


def get(uuid):
    """
    Return info on an installed image

    uuid : string
        uuid of image

    CLI Example:

    .. code-block:: bash

        salt '*' imgadm.get e42f8c84-bbea-11e2-b920-078fab2aab1f
        salt '*' imgadm.get plexinc/pms-docker:plexpass
    """
    ret = {}

    if _is_docker_uuid(uuid):
        uuid = docker_to_uuid(uuid)

    if _is_uuid(uuid):
        cmd = "imgadm get {0}".format(uuid)
        res = __salt__["cmd.run_all"](cmd, python_shell=False)
        retcode = res["retcode"]
        if retcode != 0:
            ret["Error"] = _exit_status(retcode, res["stderr"])
        else:
            ret = salt.utils.json.loads(res["stdout"])
    else:
        ret["Error"] = "{} is not a valid uuid.".format(uuid)

    return ret


def import_image(uuid, verbose=False):
    """
    Import an image from the repository

    uuid : string
        uuid to import
    verbose : boolean (False)
        toggle verbose output

    CLI Example:

    .. code-block:: bash

        salt '*' imgadm.import e42f8c84-bbea-11e2-b920-078fab2aab1f [verbose=True]
    """
    ret = {}
    cmd = "imgadm import {0}".format(uuid)
    res = __salt__["cmd.run_all"](cmd, python_shell=False)
    retcode = res["retcode"]
    if retcode != 0:
        ret["Error"] = _exit_status(retcode)
        return ret

    uuid = docker_to_uuid(uuid)
    data = _parse_image_meta(get(uuid), verbose)
    return {uuid: data}


def delete(uuid):
    """
    Remove an installed image

    uuid : string
        Specifies uuid to import

    CLI Example:

    .. code-block:: bash

        salt '*' imgadm.delete e42f8c84-bbea-11e2-b920-078fab2aab1f
    """
    ret = {}
    cmd = "imgadm delete {0}".format(uuid)
    res = __salt__["cmd.run_all"](cmd, python_shell=False)
    retcode = res["retcode"]
    if retcode != 0:
        ret["Error"] = _exit_status(retcode)
        return ret
    # output: Deleted image d5b3865c-0804-11e5-be21-dbc4ce844ddc
    result = []
    for image in res["stdout"].splitlines():
        image = [var for var in image.split(" ") if var]
        result.append(image[2])

    return result


def vacuum(verbose=False):
    """
    Remove unused images

    verbose : boolean (False)
        toggle verbose output

    CLI Example:

    .. code-block:: bash

        salt '*' imgadm.vacuum [verbose=True]
    """
    ret = {}
    cmd = "imgadm vacuum -f"
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    if retcode != 0:
        ret["Error"] = _exit_status(retcode)
        return ret
    # output: Deleted image d5b3865c-0804-11e5-be21-dbc4ce844ddc (lx-centos-6@20150601)
    result = {}
    for image in res["stdout"].splitlines():
        image = [var for var in image.split(" ") if var]
        result[image[2]] = {
            "name": image[3][1 : image[3].index("@")],
            "version": image[3][image[3].index("@") + 1 : -1],
        }
    if verbose:
        return result
    else:
        return list(result.keys())


def sources(verbose=False):
    """
    Return a list of available sources

    verbose : boolean (False)
        toggle verbose output

    .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' imgadm.sources
    """
    ret = {}
    cmd = "imgadm sources -j"
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    if retcode != 0:
        ret["Error"] = _exit_status(retcode)
        return ret

    for src in salt.utils.json.loads(res["stdout"]):
        ret[src["url"]] = src
        del src["url"]

    if not verbose:
        ret = list(ret)

    return ret


def source_delete(source):
    """
    Delete a source

    source : string
        source url to delete

    .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' imgadm.source_delete https://updates.joyent.com
    """
    ret = {}
    cmd = "imgadm sources -d {0}".format(source)
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    if retcode != 0:
        ret["Error"] = _exit_status(retcode, res["stderr"])
        return ret

    return sources(False)


def source_add(source, source_type="imgapi"):
    """
    Add a new source

    source : string
        source url to add
    source_trype : string (imgapi)
        source type, either imgapi or docker

    .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' imgadm.source_add https://updates.joyent.com
        salt '*' imgadm.source_add https://docker.io docker
    """
    ret = {}

    # NOTE: there are some undocumented deprecated source types
    #       so we just warn instead of error on those
    if source_type not in ["imgapi", "docker"]:
        log.warning("Possible unsupported imgage source type specified!")

    cmd = "imgadm sources -a {0} -t {1}".format(source, source_type)
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    if retcode != 0:
        ret["Error"] = _exit_status(retcode, res["stderr"])
        return ret

    return sources(False)


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
