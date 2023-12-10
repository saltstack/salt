"""
An engine that reads messages from the redis sentinel pubsub and sends reactor
events based on the channels they are subscribed to.

.. versionadded:: 2016.3.0

:configuration:

    Example configuration

    .. code-block:: yaml

        engines:
          - redis_sentinel:
              hosts:
                matching: 'board*'
                port: 26379
                interface: eth2
              channels:
                - '+switch-master'
                - '+odown'
                - '-odown'

:depends: redis
"""

import logging

import salt.client

try:
    import redis
except ImportError:
    redis = None

log = logging.getLogger(__name__)

__virtualname__ = "redis"


def __virtual__():
    return (
        __virtualname__
        if redis is not None
        else (False, "redis python module is not installed")
    )


class Listener:
    def __init__(self, host=None, port=None, channels=None, tag=None):
        if host is None:
            host = "localhost"
        if port is None:
            port = 26379
        if channels is None:
            channels = ["*"]
        if tag is None:
            tag = "salt/engine/redis_sentinel"
        super().__init__()
        self.tag = tag
        self.redis = redis.StrictRedis(host=host, port=port, decode_responses=True)
        self.pubsub = self.redis.pubsub()
        self.pubsub.psubscribe(channels)
        self.fire_master = salt.utils.event.get_master_event(
            __opts__, __opts__["sock_dir"]
        ).fire_event

    def work(self, item):
        ret = {"channel": item["channel"]}
        if isinstance(item["data"], int):
            ret["code"] = item["data"]
        elif item["channel"] == "+switch-master":
            ret.update(
                dict(
                    list(
                        zip(
                            ("master", "old_host", "old_port", "new_host", "new_port"),
                            item["data"].split(" "),
                        )
                    )
                )
            )
        elif item["channel"] in ("+odown", "-odown"):
            ret.update(
                dict(list(zip(("master", "host", "port"), item["data"].split(" ")[1:])))
            )
        else:
            ret = {
                "channel": item["channel"],
                "data": item["data"],
            }
        self.fire_master(ret, "{}/{}".format(self.tag, item["channel"]))

    def run(self):
        log.debug("Start Listener")
        for item in self.pubsub.listen():
            log.debug("Item: %s", item)
            self.work(item)


def start(hosts, channels, tag=None):
    if tag is None:
        tag = "salt/engine/redis_sentinel"
    with salt.client.LocalClient() as local:
        ips = local.cmd(
            hosts["matching"], "network.ip_addrs", [hosts["interface"]]
        ).values()
    client = Listener(host=ips.pop()[0], port=hosts["port"], channels=channels, tag=tag)
    client.run()
