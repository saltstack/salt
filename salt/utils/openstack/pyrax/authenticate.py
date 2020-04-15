# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import pyrax  # pylint: disable=3rd-party-module-not-gated


class Authenticate(object):
    def __init__(self, username, password, region, **kwargs):
        cloud_kwargs = {"password": password, "region": region}
        pyrax.settings.set("identity_type", kwargs.get("identity_type", "rackspace"))
        pyrax.settings.set(
            "auth_endpoint",
            kwargs.get("auth_endpoint", "https://identity.api.rackspacecloud.com/v2.0"),
        )

        pyrax.set_credentials(username, **cloud_kwargs)
        self.conn = pyrax
