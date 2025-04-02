"""
Create a salt roster out of a flat directory of files.

Each filename in the directory is a minion id.
The contents of each file is rendered using the salt renderer system.

Consider the following configuration for example:

config/master:

    ...
    roster: dir
    roster_dir: config/roster.d
    ...

Where the directory config/roster.d contains two files:

config/roster.d/minion-x:

    host: minion-x.example.com
    port: 22
    sudo: true
    user: ubuntu

config/roster.d/minion-y:

    host: minion-y.example.com
    port: 22
    sudo: true
    user: gentoo

The roster would find two minions: minion-x and minion-y, with the given host, port, sudo and user settings.

The directory roster also extends the concept of roster defaults by supporting a roster_domain value in config:

    ...
    roster_domain: example.org
    ...

If that option is set, then any roster without a 'host' setting will have an implicit host of
its minion id + '.' + the roster_domain. (The default roster_domain is the empty string,
so you can also name the files the fully qualified name of each host. However, if you do that,
then the fully qualified name of each host is also the minion id.)

This makes it possible to avoid having to specify the hostnames when you always want them to match
their minion id plus some domain.
"""

import logging
import os

import salt.loader
import salt.template
import salt.utils.verify
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


def targets(tgt, tgt_type="glob", **kwargs):
    """
    Return the targets from the directory of flat yaml files,
    checks opts for location.
    """
    roster_dir = __opts__.get("roster_dir", "/etc/salt/roster.d")
    # Match the targets before rendering to avoid opening files unnecessarily.
    raw = dict.fromkeys(os.listdir(roster_dir), "")
    log.debug("Filtering %d minions in %s", len(raw), roster_dir)
    matched_raw = __utils__["roster_matcher.targets"](raw, tgt, tgt_type, "ipv4")
    rendered = {}
    for minion_id in matched_raw:
        target_file = salt.utils.verify.clean_path(roster_dir, minion_id)
        if not os.path.exists(target_file):
            raise CommandExecutionError(f"{target_file} does not exist")
        rendered[minion_id] = _render(target_file, **kwargs)
    pruned_rendered = {id_: data for id_, data in rendered.items() if data}
    log.debug(
        "Matched %d minions with tgt=%s and tgt_type=%s."
        " Discarded %d matching filenames because they had rendering errors.",
        len(rendered),
        tgt,
        tgt_type,
        len(rendered) - len(pruned_rendered),
    )
    return pruned_rendered


def _render(roster_file, **kwargs):
    """
    Render the roster file
    """
    renderers = salt.loader.render(__opts__, {})
    domain = __opts__.get("roster_domain", "")
    try:
        result = salt.template.compile_template(
            roster_file,
            renderers,
            __opts__["renderer"],
            __opts__["renderer_blacklist"],
            __opts__["renderer_whitelist"],
            mask_value="*passw*",
            **kwargs,
        )
        result.setdefault("host", f"{os.path.basename(roster_file)}.{domain}")
        return result
    except:  # pylint: disable=W0702
        log.warning('Unable to render roster file "%s".', roster_file, exc_info=True)
        return {}
