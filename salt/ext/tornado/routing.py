# Copyright 2015 The Tornado Authors
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Flexible routing implementation.

Tornado routes HTTP requests to appropriate handlers using `Router`
class implementations. The `tornado.web.Application` class is a
`Router` implementation and may be used directly, or the classes in
this module may be used for additional flexibility. The `RuleRouter`
class can match on more criteria than `.Application`, or the `Router`
interface can be subclassed for maximum customization.

`Router` interface extends `~.httputil.HTTPServerConnectionDelegate`
to provide additional routing capabilities. This also means that any
`Router` implementation can be used directly as a ``request_callback``
for `~.httpserver.HTTPServer` constructor.

`Router` subclass must implement a ``find_handler`` method to provide
a suitable `~.httputil.HTTPMessageDelegate` instance to handle the
request:

.. code-block:: python

    class CustomRouter(Router):
        def find_handler(self, request, **kwargs):
            # some routing logic providing a suitable HTTPMessageDelegate instance
            return MessageDelegate(request.connection)

    class MessageDelegate(HTTPMessageDelegate):
        def __init__(self, connection):
            self.connection = connection

        def finish(self):
            self.connection.write_headers(
                ResponseStartLine("HTTP/1.1", 200, "OK"),
                HTTPHeaders({"Content-Length": "2"}),
                b"OK")
            self.connection.finish()

    router = CustomRouter()
    server = HTTPServer(router)

The main responsibility of `Router` implementation is to provide a
mapping from a request to `~.httputil.HTTPMessageDelegate` instance
that will handle this request. In the example above we can see that
routing is possible even without instantiating an `~.web.Application`.

For routing to `~.web.RequestHandler` implementations we need an
`~.web.Application` instance. `~.web.Application.get_handler_delegate`
provides a convenient way to create `~.httputil.HTTPMessageDelegate`
for a given request and `~.web.RequestHandler`.

Here is a simple example of how we can we route to
`~.web.RequestHandler` subclasses by HTTP method:

.. code-block:: python

    resources = {}

    class GetResource(RequestHandler):
        def get(self, path):
            if path not in resources:
                raise HTTPError(404)

            self.finish(resources[path])

    class PostResource(RequestHandler):
        def post(self, path):
            resources[path] = self.request.body

    class HTTPMethodRouter(Router):
        def __init__(self, app):
            self.app = app

        def find_handler(self, request, **kwargs):
            handler = GetResource if request.method == "GET" else PostResource
            return self.app.get_handler_delegate(request, handler, path_args=[request.path])

    router = HTTPMethodRouter(Application())
    server = HTTPServer(router)

`ReversibleRouter` interface adds the ability to distinguish between
the routes and reverse them to the original urls using route's name
and additional arguments. `~.web.Application` is itself an
implementation of `ReversibleRouter` class.

`RuleRouter` and `ReversibleRuleRouter` are implementations of
`Router` and `ReversibleRouter` interfaces and can be used for
creating rule-based routing configurations.

Rules are instances of `Rule` class. They contain a `Matcher`, which
provides the logic for determining whether the rule is a match for a
particular request and a target, which can be one of the following.

1) An instance of `~.httputil.HTTPServerConnectionDelegate`:

.. code-block:: python

    router = RuleRouter([
        Rule(PathMatches("/handler"), ConnectionDelegate()),
        # ... more rules
    ])

    class ConnectionDelegate(HTTPServerConnectionDelegate):
        def start_request(self, server_conn, request_conn):
            return MessageDelegate(request_conn)

2) A callable accepting a single argument of `~.httputil.HTTPServerRequest` type:

.. code-block:: python

    router = RuleRouter([
        Rule(PathMatches("/callable"), request_callable)
    ])

    def request_callable(request):
        request.write(b"HTTP/1.1 200 OK\\r\\nContent-Length: 2\\r\\n\\r\\nOK")
        request.finish()

3) Another `Router` instance:

.. code-block:: python

    router = RuleRouter([
        Rule(PathMatches("/router.*"), CustomRouter())
    ])

Of course a nested `RuleRouter` or a `~.web.Application` is allowed:

.. code-block:: python

    router = RuleRouter([
        Rule(HostMatches("example.com"), RuleRouter([
            Rule(PathMatches("/app1/.*"), Application([(r"/app1/handler", Handler)]))),
        ]))
    ])

    server = HTTPServer(router)

In the example below `RuleRouter` is used to route between applications:

.. code-block:: python

    app1 = Application([
        (r"/app1/handler", Handler1),
        # other handlers ...
    ])

    app2 = Application([
        (r"/app2/handler", Handler2),
        # other handlers ...
    ])

    router = RuleRouter([
        Rule(PathMatches("/app1.*"), app1),
        Rule(PathMatches("/app2.*"), app2)
    ])

    server = HTTPServer(router)

For more information on application-level routing see docs for `~.web.Application`.

.. versionadded:: 4.5

"""
# pylint: skip-file

from __future__ import absolute_import, division, print_function

import re
from functools import partial

from salt.ext.tornado import httputil
from salt.ext.tornado.httpserver import _CallableAdapter
from salt.ext.tornado.escape import url_escape, url_unescape, utf8
from salt.ext.tornado.log import app_log
from salt.ext.tornado.util import basestring_type, import_object, re_unescape, unicode_type

try:
    import typing  # noqa
except ImportError:
    pass


class Router(httputil.HTTPServerConnectionDelegate):
    """Abstract router interface."""

    def find_handler(self, request, **kwargs):
        # type: (httputil.HTTPServerRequest, typing.Any)->httputil.HTTPMessageDelegate
        """Must be implemented to return an appropriate instance of `~.httputil.HTTPMessageDelegate`
        that can serve the request.
        Routing implementations may pass additional kwargs to extend the routing logic.

        :arg httputil.HTTPServerRequest request: current HTTP request.
        :arg kwargs: additional keyword arguments passed by routing implementation.
        :returns: an instance of `~.httputil.HTTPMessageDelegate` that will be used to
            process the request.
        """
        raise NotImplementedError()

    def start_request(self, server_conn, request_conn):
        return _RoutingDelegate(self, server_conn, request_conn)


class ReversibleRouter(Router):
    """Abstract router interface for routers that can handle named routes
    and support reversing them to original urls.
    """

    def reverse_url(self, name, *args):
        """Returns url string for a given route name and arguments
        or ``None`` if no match is found.

        :arg str name: route name.
        :arg args: url parameters.
        :returns: parametrized url string for a given route name (or ``None``).
        """
        raise NotImplementedError()


class _RoutingDelegate(httputil.HTTPMessageDelegate):
    def __init__(self, router, server_conn, request_conn):
        self.server_conn = server_conn
        self.request_conn = request_conn
        self.delegate = None
        self.router = router  # type: Router

    def headers_received(self, start_line, headers):
        request = httputil.HTTPServerRequest(
            connection=self.request_conn,
            server_connection=self.server_conn,
            start_line=start_line, headers=headers)

        self.delegate = self.router.find_handler(request)
        return self.delegate.headers_received(start_line, headers)

    def data_received(self, chunk):
        return self.delegate.data_received(chunk)

    def finish(self):
        self.delegate.finish()

    def on_connection_close(self):
        self.delegate.on_connection_close()


class RuleRouter(Router):
    """Rule-based router implementation."""

    def __init__(self, rules=None):
        """Constructs a router from an ordered list of rules::

            RuleRouter([
                Rule(PathMatches("/handler"), Target),
                # ... more rules
            ])

        You can also omit explicit `Rule` constructor and use tuples of arguments::

            RuleRouter([
                (PathMatches("/handler"), Target),
            ])

        `PathMatches` is a default matcher, so the example above can be simplified::

            RuleRouter([
                ("/handler", Target),
            ])

        In the examples above, ``Target`` can be a nested `Router` instance, an instance of
        `~.httputil.HTTPServerConnectionDelegate` or an old-style callable, accepting a request argument.

        :arg rules: a list of `Rule` instances or tuples of `Rule`
            constructor arguments.
        """
        self.rules = []  # type: typing.List[Rule]
        if rules:
            self.add_rules(rules)

    def add_rules(self, rules):
        """Appends new rules to the router.

        :arg rules: a list of Rule instances (or tuples of arguments, which are
            passed to Rule constructor).
        """
        for rule in rules:
            if isinstance(rule, (tuple, list)):
                assert len(rule) in (2, 3, 4)
                if isinstance(rule[0], basestring_type):
                    rule = Rule(PathMatches(rule[0]), *rule[1:])
                else:
                    rule = Rule(*rule)

            self.rules.append(self.process_rule(rule))

    def process_rule(self, rule):
        """Override this method for additional preprocessing of each rule.

        :arg Rule rule: a rule to be processed.
        :returns: the same or modified Rule instance.
        """
        return rule

    def find_handler(self, request, **kwargs):
        for rule in self.rules:
            target_params = rule.matcher.match(request)
            if target_params is not None:
                if rule.target_kwargs:
                    target_params['target_kwargs'] = rule.target_kwargs

                delegate = self.get_target_delegate(
                    rule.target, request, **target_params)

                if delegate is not None:
                    return delegate

        return None

    def get_target_delegate(self, target, request, **target_params):
        """Returns an instance of `~.httputil.HTTPMessageDelegate` for a
        Rule's target. This method is called by `~.find_handler` and can be
        extended to provide additional target types.

        :arg target: a Rule's target.
        :arg httputil.HTTPServerRequest request: current request.
        :arg target_params: additional parameters that can be useful
            for `~.httputil.HTTPMessageDelegate` creation.
        """
        if isinstance(target, Router):
            return target.find_handler(request, **target_params)

        elif isinstance(target, httputil.HTTPServerConnectionDelegate):
            return target.start_request(request.server_connection, request.connection)

        elif callable(target):
            return _CallableAdapter(
                partial(target, **target_params), request.connection
            )

        return None


class ReversibleRuleRouter(ReversibleRouter, RuleRouter):
    """A rule-based router that implements ``reverse_url`` method.

    Each rule added to this router may have a ``name`` attribute that can be
    used to reconstruct an original uri. The actual reconstruction takes place
    in a rule's matcher (see `Matcher.reverse`).
    """

    def __init__(self, rules=None):
        self.named_rules = {}  # type: typing.Dict[str]
        super(ReversibleRuleRouter, self).__init__(rules)

    def process_rule(self, rule):
        rule = super(ReversibleRuleRouter, self).process_rule(rule)

        if rule.name:
            if rule.name in self.named_rules:
                app_log.warning(
                    "Multiple handlers named %s; replacing previous value",
                    rule.name)
            self.named_rules[rule.name] = rule

        return rule

    def reverse_url(self, name, *args):
        if name in self.named_rules:
            return self.named_rules[name].matcher.reverse(*args)

        for rule in self.rules:
            if isinstance(rule.target, ReversibleRouter):
                reversed_url = rule.target.reverse_url(name, *args)
                if reversed_url is not None:
                    return reversed_url

        return None


class Rule(object):
    """A routing rule."""

    def __init__(self, matcher, target, target_kwargs=None, name=None):
        """Constructs a Rule instance.

        :arg Matcher matcher: a `Matcher` instance used for determining
            whether the rule should be considered a match for a specific
            request.
        :arg target: a Rule's target (typically a ``RequestHandler`` or
            `~.httputil.HTTPServerConnectionDelegate` subclass or even a nested `Router`,
            depending on routing implementation).
        :arg dict target_kwargs: a dict of parameters that can be useful
            at the moment of target instantiation (for example, ``status_code``
            for a ``RequestHandler`` subclass). They end up in
            ``target_params['target_kwargs']`` of `RuleRouter.get_target_delegate`
            method.
        :arg str name: the name of the rule that can be used to find it
            in `ReversibleRouter.reverse_url` implementation.
        """
        if isinstance(target, str):
            # import the Module and instantiate the class
            # Must be a fully qualified name (module.ClassName)
            target = import_object(target)

        self.matcher = matcher  # type: Matcher
        self.target = target
        self.target_kwargs = target_kwargs if target_kwargs else {}
        self.name = name

    def reverse(self, *args):
        return self.matcher.reverse(*args)

    def __repr__(self):
        return '%s(%r, %s, kwargs=%r, name=%r)' % \
               (self.__class__.__name__, self.matcher,
                self.target, self.target_kwargs, self.name)


class Matcher(object):
    """Represents a matcher for request features."""

    def match(self, request):
        """Matches current instance against the request.

        :arg httputil.HTTPServerRequest request: current HTTP request
        :returns: a dict of parameters to be passed to the target handler
            (for example, ``handler_kwargs``, ``path_args``, ``path_kwargs``
            can be passed for proper `~.web.RequestHandler` instantiation).
            An empty dict is a valid (and common) return value to indicate a match
            when the argument-passing features are not used.
            ``None`` must be returned to indicate that there is no match."""
        raise NotImplementedError()

    def reverse(self, *args):
        """Reconstructs full url from matcher instance and additional arguments."""
        return None


class AnyMatches(Matcher):
    """Matches any request."""

    def match(self, request):
        return {}


class HostMatches(Matcher):
    """Matches requests from hosts specified by ``host_pattern`` regex."""

    def __init__(self, host_pattern):
        if isinstance(host_pattern, basestring_type):
            if not host_pattern.endswith("$"):
                host_pattern += "$"
            self.host_pattern = re.compile(host_pattern)
        else:
            self.host_pattern = host_pattern

    def match(self, request):
        if self.host_pattern.match(request.host_name):
            return {}

        return None


class DefaultHostMatches(Matcher):
    """Matches requests from host that is equal to application's default_host.
    Always returns no match if ``X-Real-Ip`` header is present.
    """

    def __init__(self, application, host_pattern):
        self.application = application
        self.host_pattern = host_pattern

    def match(self, request):
        # Look for default host if not behind load balancer (for debugging)
        if "X-Real-Ip" not in request.headers:
            if self.host_pattern.match(self.application.default_host):
                return {}
        return None


class PathMatches(Matcher):
    """Matches requests with paths specified by ``path_pattern`` regex."""

    def __init__(self, path_pattern):
        if isinstance(path_pattern, basestring_type):
            if not path_pattern.endswith('$'):
                path_pattern += '$'
            self.regex = re.compile(path_pattern)
        else:
            self.regex = path_pattern

        assert len(self.regex.groupindex) in (0, self.regex.groups), \
            ("groups in url regexes must either be all named or all "
             "positional: %r" % self.regex.pattern)

        self._path, self._group_count = self._find_groups()

    def match(self, request):
        match = self.regex.match(request.path)
        if match is None:
            return None
        if not self.regex.groups:
            return {}

        path_args, path_kwargs = [], {}

        # Pass matched groups to the handler.  Since
        # match.groups() includes both named and
        # unnamed groups, we want to use either groups
        # or groupdict but not both.
        if self.regex.groupindex:
            path_kwargs = dict(
                (str(k), _unquote_or_none(v))
                for (k, v) in match.groupdict().items())
        else:
            path_args = [_unquote_or_none(s) for s in match.groups()]

        return dict(path_args=path_args, path_kwargs=path_kwargs)

    def reverse(self, *args):
        if self._path is None:
            raise ValueError("Cannot reverse url regex " + self.regex.pattern)
        assert len(args) == self._group_count, "required number of arguments " \
                                               "not found"
        if not len(args):
            return self._path
        converted_args = []
        for a in args:
            if not isinstance(a, (unicode_type, bytes)):
                a = str(a)
            converted_args.append(url_escape(utf8(a), plus=False))
        return self._path % tuple(converted_args)

    def _find_groups(self):
        """Returns a tuple (reverse string, group count) for a url.

        For example: Given the url pattern /([0-9]{4})/([a-z-]+)/, this method
        would return ('/%s/%s/', 2).
        """
        pattern = self.regex.pattern
        if pattern.startswith('^'):
            pattern = pattern[1:]
        if pattern.endswith('$'):
            pattern = pattern[:-1]

        if self.regex.groups != pattern.count('('):
            # The pattern is too complicated for our simplistic matching,
            # so we can't support reversing it.
            return None, None

        pieces = []
        for fragment in pattern.split('('):
            if ')' in fragment:
                paren_loc = fragment.index(')')
                if paren_loc >= 0:
                    pieces.append('%s' + fragment[paren_loc + 1:])
            else:
                try:
                    unescaped_fragment = re_unescape(fragment)
                except ValueError as exc:
                    # If we can't unescape part of it, we can't
                    # reverse this url.
                    return (None, None)
                pieces.append(unescaped_fragment)

        return ''.join(pieces), self.regex.groups


class URLSpec(Rule):
    """Specifies mappings between URLs and handlers.

    .. versionchanged: 4.5
       `URLSpec` is now a subclass of a `Rule` with `PathMatches` matcher and is preserved for
       backwards compatibility.
    """
    def __init__(self, pattern, handler, kwargs=None, name=None):
        """Parameters:

        * ``pattern``: Regular expression to be matched. Any capturing
          groups in the regex will be passed in to the handler's
          get/post/etc methods as arguments (by keyword if named, by
          position if unnamed. Named and unnamed capturing groups may
          may not be mixed in the same rule).

        * ``handler``: `~.web.RequestHandler` subclass to be invoked.

        * ``kwargs`` (optional): A dictionary of additional arguments
          to be passed to the handler's constructor.

        * ``name`` (optional): A name for this handler.  Used by
          `~.web.Application.reverse_url`.

        """
        super(URLSpec, self).__init__(PathMatches(pattern), handler, kwargs, name)

        self.regex = self.matcher.regex
        self.handler_class = self.target
        self.kwargs = kwargs

    def __repr__(self):
        return '%s(%r, %s, kwargs=%r, name=%r)' % \
               (self.__class__.__name__, self.regex.pattern,
                self.handler_class, self.kwargs, self.name)


def _unquote_or_none(s):
    """None-safe wrapper around url_unescape to handle unmatched optional
    groups correctly.

    Note that args are passed as bytes so the handler can decide what
    encoding to use.
    """
    if s is None:
        return s
    return url_unescape(s, encoding=None, plus=False)
