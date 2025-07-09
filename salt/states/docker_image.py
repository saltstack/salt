"""
Management of Docker images

.. versionadded:: 2017.7.0

:depends: docker_ Python module

.. note::
    Older releases of the Python bindings for Docker were called docker-py_ in
    PyPI. All releases of docker_, and releases of docker-py_ >= 1.6.0 are
    supported. These python bindings can easily be installed using
    :py:func:`pip.install <salt.modules.pip.install>`:

    .. code-block:: bash

        salt myminion pip.install docker

    To upgrade from docker-py_ to docker_, you must first uninstall docker-py_,
    and then install docker_:

    .. code-block:: bash

        salt myminion pip.uninstall docker-py
        salt myminion pip.install docker

.. _docker: https://pypi.python.org/pypi/docker
.. _docker-py: https://pypi.python.org/pypi/docker-py

These states were moved from the :mod:`docker <salt.states.docker>` state
module (formerly called **dockerng**) in the 2017.7.0 release.

.. note::
    To pull from a Docker registry, authentication must be configured. See
    :ref:`here <docker-authentication>` for more information on how to
    configure access to docker registries in :ref:`Pillar <pillar>` data.
"""

import logging

import salt.utils.args
import salt.utils.dockermod
from salt.exceptions import CommandExecutionError

# Enable proper logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "docker_image"
__virtual_aliases__ = ("moby_image",)


def __virtual__():
    """
    Only load if the docker execution module is available
    """
    if "docker.version" in __salt__:
        return __virtualname__
    return (False, __salt__.missing_fun_string("docker.version"))


def present(
    name,
    tag=None,
    build=None,
    load=None,
    force=False,
    insecure_registry=False,
    client_timeout=salt.utils.dockermod.CLIENT_TIMEOUT,
    dockerfile=None,
    sls=None,
    base="opensuse/python",
    saltenv="base",
    pillarenv=None,
    pillar=None,
    **kwargs,
):
    """
    .. versionchanged:: 2018.3.0
        The ``tag`` argument has been added. It is now required unless pulling
        from a registry.

    Ensure that an image is present. The image can either be pulled from a
    Docker registry, built from a Dockerfile, loaded from a saved image, or
    built by running SLS files against a base image.

    If none of the ``build``, ``load``, or ``sls`` arguments are used, then Salt
    will pull from the :ref:`configured registries <docker-authentication>`. If
    the specified image already exists, it will not be pulled unless ``force``
    is set to ``True``. Here is an example of a state that will pull an image
    from the Docker Hub:

    .. code-block:: yaml

        myuser/myimage:
          docker_image.present:
            - tag: mytag

    name
        The name of the docker image.

    tag
        Tag name for the image. Required when using ``build``, ``load``, or
        ``sls`` to create the image, but optional if pulling from a repository.

        .. versionadded:: 2018.3.0

    build
        Path to directory on the Minion containing a Dockerfile

        .. code-block:: yaml

            myuser/myimage:
              docker_image.present:
                - build: /home/myuser/docker/myimage
                - tag: mytag

            myuser/myimage:
              docker_image.present:
                - build: /home/myuser/docker/myimage
                - tag: mytag
                - dockerfile: Dockerfile.alternative

        The image will be built using :py:func:`docker.build
        <salt.modules.dockermod.build>` and the specified image name and tag
        will be applied to it.

        .. versionadded:: 2016.11.0
        .. versionchanged:: 2018.3.0
            The ``tag`` must be manually specified using the ``tag`` argument.

    load
        Loads a tar archive created with :py:func:`docker.save
        <salt.modules.dockermod.save>` (or the ``docker save`` Docker CLI
        command), and assigns it the specified repo and tag.

        .. code-block:: yaml

            myuser/myimage:
              docker_image.present:
                - load: salt://path/to/image.tar
                - tag: mytag

        .. versionchanged:: 2018.3.0
            The ``tag`` must be manually specified using the ``tag`` argument.

    force
        Set this parameter to ``True`` to force Salt to pull/build/load the
        image even if it is already present.

    insecure_registry
        If ``True``, the Docker client will permit the use of insecure
        (non-HTTPS) registries.

    client_timeout
        Timeout in seconds for the Docker client. This is not a timeout for
        the state, but for receiving a response from the API.

    dockerfile
        Allows for an alternative Dockerfile to be specified.  Path to alternative
        Dockefile is relative to the build path for the Docker container.

        .. versionadded:: 2016.11.0

    sls
        Allow for building of image with :py:func:`docker.sls_build
        <salt.modules.dockermod.sls_build>` by specifying the SLS files with
        which to build. This can be a list or comma-separated string.

        .. code-block:: yaml

            myuser/myimage:
              docker_image.present:
                - tag: latest
                - sls:
                    - webapp1
                    - webapp2
                - base: centos
                - saltenv: base

        .. versionadded:: 2017.7.0
        .. versionchanged:: 2018.3.0
            The ``tag`` must be manually specified using the ``tag`` argument.

    base
        Base image with which to start :py:func:`docker.sls_build
        <salt.modules.dockermod.sls_build>`

        .. versionadded:: 2017.7.0

    saltenv
        Specify the environment from which to retrieve the SLS indicated by the
        `mods` parameter.

        .. versionadded:: 2017.7.0
        .. versionchanged:: 2018.3.0
            Now uses the effective saltenv if not explicitly passed. In earlier
            versions, ``base`` was assumed as a default.

    pillarenv
        Specify a Pillar environment to be used when applying states. This
        can also be set in the minion config file using the
        :conf_minion:`pillarenv` option. When neither the
        :conf_minion:`pillarenv` minion config option nor this CLI argument is
        used, all Pillar environments will be merged together.

        .. versionadded:: 2018.3.0

    pillar
        Custom Pillar values, passed as a dictionary of key-value pairs

        .. note::
            Values passed this way will override Pillar values set via
            ``pillar_roots`` or an external Pillar source.

        .. versionadded:: 2018.3.0

    kwargs
        Additional keyword arguments to pass to
        :py:func:`docker.build <salt.modules.dockermod.build>`
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    if not isinstance(name, str):
        name = str(name)

    # At most one of the args that result in an image being built can be used
    num_build_args = len([x for x in (build, load, sls) if x is not None])
    if num_build_args > 1:
        ret["comment"] = "Only one of 'build', 'load', or 'sls' is permitted."
        return ret
    elif num_build_args == 1:
        # If building, we need the tag to be specified
        if not tag:
            ret["comment"] = (
                "The 'tag' argument is required if any one of 'build', "
                "'load', or 'sls' is used."
            )
            return ret
        if not isinstance(tag, str):
            tag = str(tag)
        full_image = ":".join((name, tag))
    else:
        if tag:
            name = f"{name}:{tag}"
        full_image = name

    try:
        image_info = __salt__["docker.inspect_image"](full_image)
    except CommandExecutionError as exc:
        msg = str(exc)
        if "404" in msg:
            # Image not present
            image_info = None
        else:
            ret["comment"] = msg
            return ret

    if image_info is not None:
        # Specified image is present
        if not force:
            ret["result"] = True
            ret["comment"] = f"Image {full_image} already present"
            return ret

    if build or sls:
        action = "built"
    elif load:
        action = "loaded"
    else:
        action = "pulled"

    if __opts__["test"]:
        ret["result"] = None
        if (image_info is not None and force) or image_info is None:
            ret["comment"] = f"Image {full_image} will be {action}"
            return ret

    if build:
        # Get the functions default value and args
        argspec = salt.utils.args.get_function_argspec(__salt__["docker.build"])
        # Map any if existing args from kwargs into the build_args dictionary
        build_args = dict(list(zip(argspec.args, argspec.defaults)))
        for k in build_args:
            if k in kwargs.get("kwargs", {}):
                build_args[k] = kwargs.get("kwargs", {}).get(k)
        try:
            # map values passed from the state to the build args
            build_args["path"] = build
            build_args["repository"] = name
            build_args["tag"] = tag
            build_args["dockerfile"] = dockerfile
            image_update = __salt__["docker.build"](**build_args)
        except Exception as exc:  # pylint: disable=broad-except
            ret["comment"] = "Encountered error building {} as {}: {}".format(
                build, full_image, exc
            )
            return ret
        if image_info is None or image_update["Id"] != image_info["Id"][:12]:
            ret["changes"] = image_update

    elif sls:
        _locals = locals()
        sls_build_kwargs = {
            k: _locals[k]
            for k in ("saltenv", "pillarenv", "pillar")
            if _locals[k] is not None
        }
        try:
            image_update = __salt__["docker.sls_build"](
                repository=name, tag=tag, base=base, mods=sls, **sls_build_kwargs
            )
        except Exception as exc:  # pylint: disable=broad-except
            ret["comment"] = (
                "Encountered error using SLS {} for building {}: {}".format(
                    sls, full_image, exc
                )
            )
            return ret
        if image_info is None or image_update["Id"] != image_info["Id"][:12]:
            ret["changes"] = image_update

    elif load:
        try:
            image_update = __salt__["docker.load"](path=load, repository=name, tag=tag)
        except Exception as exc:  # pylint: disable=broad-except
            ret["comment"] = "Encountered error loading {} as {}: {}".format(
                load, full_image, exc
            )
            return ret
        if image_info is None or image_update.get("Layers", []):
            ret["changes"] = image_update

    else:
        try:
            image_update = __salt__["docker.pull"](
                name, insecure_registry=insecure_registry, client_timeout=client_timeout
            )
        except Exception as exc:  # pylint: disable=broad-except
            ret["comment"] = f"Encountered error pulling {full_image}: {exc}"
            return ret
        if (
            image_info is not None
            and image_info["Id"][:12]
            == image_update.get("Layers", {}).get("Already_Pulled", [None])[0]
        ):
            # Image was pulled again (because of force) but was also
            # already there. No new image was available on the registry.
            pass
        elif image_info is None or image_update.get("Layers", {}).get("Pulled"):
            # Only add to the changes dict if layers were pulled
            ret["changes"] = image_update

    error = False

    try:
        __salt__["docker.inspect_image"](full_image)
    except CommandExecutionError as exc:
        msg = str(exc)
        if "404" not in msg:
            error = "Failed to inspect image '{}' after it was {}: {}".format(
                full_image, action, msg
            )

    if error:
        ret["comment"] = error
    else:
        ret["result"] = True
        if not ret["changes"]:
            ret["comment"] = "Image '{}' was {}, but there were no changes".format(
                name, action
            )
        else:
            ret["comment"] = f"Image '{full_image}' was {action}"
    return ret


def absent(name=None, images=None, force=False):
    """
    Ensure that an image is absent from the Minion. Image names can be
    specified either using ``repo:tag`` notation, or just the repo name (in
    which case a tag of ``latest`` is assumed).

    name
        The name of the docker image.

    images
        Run this state on more than one image at a time. The following two
        examples accomplish the same thing:

        .. code-block:: yaml

            remove_images:
              docker_image.absent:
                - names:
                  - busybox
                  - centos:6
                  - nginx

        .. code-block:: yaml

            remove_images:
              docker_image.absent:
                - images:
                  - busybox
                  - centos:6
                  - nginx

        However, the second example will be a bit quicker since Salt will do
        all the deletions in a single run, rather than executing the state
        separately on each image (as it would in the first example).

    force
        Salt will fail to remove any images currently in use by a container.
        Set this option to true to remove the image even if it is already
        present.

        .. note::

            This option can also be overridden by Pillar data. If the Minion
            has a pillar variable named ``docker.running.force`` which is
            set to ``True``, it will turn on this option. This pillar variable
            can even be set at runtime. For example:

            .. code-block:: bash

                salt myminion state.sls docker_stuff pillar="{docker.force: True}"

            If this pillar variable is present and set to ``False``, then it
            will turn off this option.

            For more granular control, setting a pillar variable named
            ``docker.force.image_name`` will affect only the named image.
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    if not name and not images:
        ret["comment"] = "One of 'name' and 'images' must be provided"
        return ret
    elif images is not None:
        targets = images
    elif name:
        targets = [name]

    to_delete = []
    for target in targets:
        resolved_tag = __salt__["docker.resolve_tag"](target)
        if resolved_tag is not False:
            to_delete.append(resolved_tag)

    if not to_delete:
        ret["result"] = True
        if len(targets) == 1:
            ret["comment"] = f"Image {name} is not present"
        else:
            ret["comment"] = "All specified images are not present"
        return ret

    if __opts__["test"]:
        ret["result"] = None
        if len(to_delete) == 1:
            ret["comment"] = f"Image {to_delete[0]} will be removed"
        else:
            ret["comment"] = "The following images will be removed: {}".format(
                ", ".join(to_delete)
            )
        return ret

    result = __salt__["docker.rmi"](*to_delete, force=force)
    post_tags = __salt__["docker.list_tags"]()
    failed = [x for x in to_delete if x in post_tags]

    if failed:
        if [x for x in to_delete if x not in post_tags]:
            ret["changes"] = result
            ret["comment"] = "The following image(s) failed to be removed: {}".format(
                ", ".join(failed)
            )
        else:
            ret["comment"] = "None of the specified images were removed"
            if "Errors" in result:
                ret["comment"] += ". The following errors were encountered: {}".format(
                    "; ".join(result["Errors"])
                )
    else:
        ret["changes"] = result
        if len(to_delete) == 1:
            ret["comment"] = f"Image {to_delete[0]} was removed"
        else:
            ret["comment"] = "The following images were removed: {}".format(
                ", ".join(to_delete)
            )
        ret["result"] = True

    return ret


def mod_watch(name, sfun=None, **kwargs):
    """
    The docker_image  watcher, called to invoke the watch command.

    .. note::
        This state exists to support special handling of the ``watch``
        :ref:`requisite <requisites>`. It should not be called directly.

        Parameters for this function should be set by the state being triggered.
    """
    if sfun == "present":
        # Force image to be updated
        kwargs["force"] = True
        return present(name, **kwargs)

    return {
        "name": name,
        "changes": {},
        "result": False,
        "comment": f"watch requisite is not implemented for {sfun}",
    }
