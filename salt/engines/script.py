# -*- coding: utf-8 -*-
"""
Send events based on a script's stdout

Example Config

.. code-block:: yaml

    engines:
      - script:
          cmd: /some/script.py -a 1 -b 2
          output: json
          interval: 5

Script engine configs:

    cmd: Script or command to execute
    output: Any available saltstack deserializer
    interval: How often in seconds to execute the command

"""

from __future__ import absolute_import, print_function

import logging
import shlex
import subprocess
import time

import salt.loader

# import salt libs
import salt.utils.event
import salt.utils.process
from salt.exceptions import CommandExecutionError
from salt.ext import six

log = logging.getLogger(__name__)


def _read_stdout(proc):
    """
    Generator that returns stdout
    """
    for line in iter(proc.stdout.readline, ""):
        yield line


def _get_serializer(output):
    """
    Helper to return known serializer based on
    pass output argument
    """
    serializers = salt.loader.serializers(__opts__)
    try:
        return getattr(serializers, output)
    except AttributeError:
        raise CommandExecutionError(
            "Unknown serializer `{}` found for output option".format(output)
        )


def start(cmd, output="json", interval=1):
    """
    Parse stdout of a command and generate an event

    The script engine will scrap stdout of the
    given script and generate an event based on the
    presence of the 'tag' key and its value.

    If there is a data obj available, that will also
    be fired along with the tag.

    Example:

        Given the following json output from a script:

            .. code-block:: json

                { "tag" : "lots/of/tacos",
                "data" : { "toppings" : "cilantro" }
                }

        This will fire the event 'lots/of/tacos'
        on the event bus with the data obj as is.

    :param cmd: The command to execute
    :param output: How to deserialize stdout of the script
    :param interval: How often to execute the script
    """
    try:
        cmd = shlex.split(cmd)
    except AttributeError:
        cmd = shlex.split(six.text_type(cmd))
    log.debug("script engine using command %s", cmd)

    serializer = _get_serializer(output)

    if __opts__.get("__role") == "master":
        fire_master = salt.utils.event.get_master_event(
            __opts__, __opts__["sock_dir"]
        ).fire_event
    else:
        fire_master = __salt__["event.send"]

    while True:

        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
            )

            log.debug("Starting script with pid %d", proc.pid)

            for raw_event in _read_stdout(proc):
                log.debug(raw_event)

                event = serializer.deserialize(raw_event)
                tag = event.get("tag", None)
                data = event.get("data", {})

                if data and "id" not in data:
                    data["id"] = __opts__["id"]

                if tag:
                    log.info("script engine firing event with tag %s", tag)
                    fire_master(tag=tag, data=data)

            log.debug("Closing script with pid %d", proc.pid)
            proc.stdout.close()
            rc = proc.wait()
            if rc:
                raise subprocess.CalledProcessError(rc, cmd)

        except subprocess.CalledProcessError as e:
            log.error(e)
        finally:
            if proc.poll is None:
                proc.terminate()

        time.sleep(interval)
