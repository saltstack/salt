# -*- coding: utf-8 -*-
"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)

    salt.config.schemas.minion
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    Minion configuration schema
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

from salt.config.schemas.common import IncludeConfig, MinionDefaultInclude

# Import salt libs
from salt.utils.schema import IPv4Item, Schema

# XXX: THIS IS WAY TOO MINIMAL, BUT EXISTS TO IMPLEMENT salt-ssh


class MinionConfiguration(Schema):

    # Because salt's configuration is very permissive with additioal
    # configuration settings, let's allow them in the schema or validation
    # would fail
    __allow_additional_items__ = True

    interface = IPv4Item(title="Interface")

    default_include = MinionDefaultInclude()
    include = IncludeConfig()
