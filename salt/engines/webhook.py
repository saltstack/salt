"""
Send events from webhook api
"""

import asyncio

import aiohttp.web

import salt.transport.base
import salt.utils.event
from salt.utils.asynchronous import get_io_loop


def start(address=None, port=5000, ssl_crt=None, ssl_key=None):
    """
    Api to listen for webhooks to send to the reactor.

    Implement the webhook behavior in an engine.
    :py:class:`rest_cherrypy Webhook docs <salt.netapi.rest_cherrypy.app.Webhook>`

    Unlike the rest_cherrypy Webhook, this is only an unauthenticated webhook
    endpoint.  If an authenticated webhook endpoint is needed, use the salt-api
    webhook which runs on the master and authenticates through eauth.

    .. note: This is really meant to be used on the minion, because salt-api
             needs to be run on the master for use with eauth.

    .. warning:: Unauthenticated endpoint

        This engine sends webhook calls to the event stream.  If the engine is
        running on a minion with `file_client: local` the event is sent to the
        minion event stream.  Otherwise it is sent to the master event stream.

    Example Config

    .. code-block:: yaml

        engines:
          - webhook: {}

    .. code-block:: yaml

        engines:
          - webhook:
              port: 8000
              address: 10.128.1.145
              ssl_crt: /etc/pki/tls/certs/localhost.crt
              ssl_key: /etc/pki/tls/certs/localhost.key

    .. note: For making an unsigned key, use the following command
             `salt-call --local tls.create_self_signed_cert`
    """
    if __opts__.get("__role") == "master":
        fire_master = salt.utils.event.get_master_event(
            __opts__, __opts__["sock_dir"]
        ).fire_event
    else:
        fire_master = None

    def fire(tag, msg):
        """
        How to fire the event
        """
        if fire_master:
            fire_master(msg, tag)
        else:
            __salt__["event.send"](tag, msg)

    async def webhook_handler(request):
        tag = request.match_info.get("tag", "")
        body = await request.read()
        headers = dict(request.headers)
        payload = {"headers": headers, "body": body}
        fire("salt/engines/hook/" + tag, payload)
        return aiohttp.web.Response(status=200)

    async def run_server():
        app = aiohttp.web.Application()
        app.router.add_post("/{tag:.*}", webhook_handler)
        runner = aiohttp.web.AppRunner(app)
        await runner.setup()
        ssl_context = None
        if ssl_crt and ssl_key:
            ssl_context = salt.transport.base.ssl_context(
                {"cert": ssl_crt, "key": ssl_key}, server_side=True
            )
        site = aiohttp.web.TCPSite(
            runner, address or "0.0.0.0", port, ssl_context=ssl_context
        )
        await site.start()
        await asyncio.Event().wait()

    loop_adapter = get_io_loop()
    loop_adapter.spawn_callback(run_server)
    try:
        loop_adapter.start()
    finally:
        loop_adapter.stop()
