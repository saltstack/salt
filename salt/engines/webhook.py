"""
Send events from webhook api
"""

import tornado.httpserver
import tornado.ioloop
import tornado.web

import salt.utils.event


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

    class WebHook(tornado.web.RequestHandler):  # pylint: disable=abstract-method
        def post(self, tag):  # pylint: disable=arguments-differ
            body = self.request.body
            headers = self.request.headers
            payload = {
                "headers": headers if isinstance(headers, dict) else dict(headers),
                "body": body,
            }
            fire("salt/engines/hook/" + tag, payload)

    application = tornado.web.Application([(r"/(.*)", WebHook)])
    ssl_options = None
    if all([ssl_crt, ssl_key]):
        ssl_options = {"certfile": ssl_crt, "keyfile": ssl_key}
    io_loop = tornado.ioloop.IOLoop()
    http_server = tornado.httpserver.HTTPServer(application, ssl_options=ssl_options)
    http_server.listen(port, address=address)
    io_loop.start()
