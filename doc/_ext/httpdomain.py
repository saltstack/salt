"""
    sphinxcontrib.httpdomain
    ~~~~~~~~~~~~~~~~~~~~~~~~

    The HTTP domain for documenting RESTful HTTP APIs.

    :copyright: Copyright 2011 by Hong Minhee
    :license: BSD, see LICENSE for details.

"""

import re

from docutils import nodes
from docutils.parsers.rst.roles import set_classes

from pygments.lexer import RegexLexer, bygroups
from pygments.lexers import get_lexer_by_name
from pygments.token import Literal, Text,  Operator, Keyword, Name, Number
from pygments.util import ClassNotFound

from sphinx import addnodes
from sphinx.roles import XRefRole
from sphinx.domains import Domain, ObjType, Index
from sphinx.directives import ObjectDescription
from sphinx.util.nodes import make_refnode
from sphinx.util.docfields import GroupedField, TypedField


class DocRef(object):
    """Represents a link to an RFC which defines an HTTP method."""

    def __init__(self, base_url, anchor, section):
        """Stores the specified attributes which represent a URL which links to
        an RFC which defines an HTTP method.

        """
        self.base_url = base_url
        self.anchor = anchor
        self.section = section

    def __repr__(self):
        """Returns the URL which this object represents, which points to the
        location of the RFC which defines some HTTP method.

        """
        return '{0}#{1}{2}'.format(self.base_url, self.anchor, self.section)


#: The URL of the HTTP/1.1 RFC which defines the HTTP methods OPTIONS, GET,
#: HEAD, POST, PUT, DELETE, TRACE, and CONNECT.
RFC2616 = 'http://www.w3.org/Protocols/rfc2616/rfc2616-sec9.html'

#: The name to use for section anchors in RFC2616.
RFC2616ANCHOR = 'sec'

#: The URL of the RFC which defines the HTTP PATCH method.
RFC5789 = 'http://tools.ietf.org/html/rfc5789'

#: The name to use for section anchors in RFC5789.
RFC5789ANCHOR = 'section-'

#: Mapping from lowercase HTTP method name to :class:`DocRef` object which
#: maintains the URL which points to the section of the RFC which defines that
#: HTTP method.
DOCREFS = {
    'patch': DocRef(RFC5789, RFC5789ANCHOR, 2),
    'options': DocRef(RFC2616, RFC2616ANCHOR, 9.2),
    'get': DocRef(RFC2616, RFC2616ANCHOR, 9.3),
    'head': DocRef(RFC2616, RFC2616ANCHOR, 9.4),
    'post': DocRef(RFC2616, RFC2616ANCHOR, 9.5),
    'put': DocRef(RFC2616, RFC2616ANCHOR, 9.6),
    'delete': DocRef(RFC2616, RFC2616ANCHOR, 9.7),
    'trace': DocRef(RFC2616, RFC2616ANCHOR, 9.8),
    'connect': DocRef(RFC2616, RFC2616ANCHOR, 9.9)
}

HTTP_STATUS_CODES = {
    100: 'Continue',
    101: 'Switching Protocols',
    102: 'Processing',
    200: 'OK',
    201: 'Created',
    202: 'Accepted',
    203: 'Non Authoritative Information',
    204: 'No Content',
    205: 'Reset Content',
    206: 'Partial Content',
    207: 'Multi Status',
    226: 'IM Used',              # see RFC 3229
    300: 'Multiple Choices',
    301: 'Moved Permanently',
    302: 'Found',
    303: 'See Other',
    304: 'Not Modified',
    305: 'Use Proxy',
    307: 'Temporary Redirect',
    400: 'Bad Request',
    401: 'Unauthorized',
    402: 'Payment Required',     # unused
    403: 'Forbidden',
    404: 'Not Found',
    405: 'Method Not Allowed',
    406: 'Not Acceptable',
    407: 'Proxy Authentication Required',
    408: 'Request Timeout',
    409: 'Conflict',
    410: 'Gone',
    411: 'Length Required',
    412: 'Precondition Failed',
    413: 'Request Entity Too Large',
    414: 'Request URI Too Long',
    415: 'Unsupported Media Type',
    416: 'Requested Range Not Satisfiable',
    417: 'Expectation Failed',
    418: "I'm a teapot",        # see RFC 2324
    422: 'Unprocessable Entity',
    423: 'Locked',
    424: 'Failed Dependency',
    426: 'Upgrade Required',
    449: 'Retry With',           # proprietary MS extension
    500: 'Internal Server Error',
    501: 'Not Implemented',
    502: 'Bad Gateway',
    503: 'Service Unavailable',
    504: 'Gateway Timeout',
    505: 'HTTP Version Not Supported',
    507: 'Insufficient Storage',
    510: 'Not Extended'
}

http_sig_param_re = re.compile(r'\((?:(?P<type>[^:)]+):)?(?P<name>[\w_]+)\)',
                               re.VERBOSE)


def http_resource_anchor(method, path):
    path = re.sub(r'[<>:/]', '-', path)
    return method.lower() + '-' + path


class HTTPResource(ObjectDescription):

    doc_field_types = [
        TypedField('parameter', label='Parameters',
                   names=('param', 'parameter', 'arg', 'argument'),
                   typerolename='obj', typenames=('paramtype', 'type')),
        TypedField('jsonparameter', label='JSON Parameters',
                   names=('jsonparameter', 'jsonparam', 'json'),
                   typerolename='obj', typenames=('jsonparamtype', 'jsontype')),
        TypedField('queryparameter', label='Query Parameters',
                     names=('queryparameter', 'queryparam', 'qparam', 'query'),
                     typerolename='obj', typenames=('queryparamtype', 'querytype', 'qtype')),
        GroupedField('formparameter', label='Form Parameters',
                     names=('formparameter', 'formparam', 'fparam', 'form')),
        GroupedField('requestheader', label='Request Headers',
                     rolename='mailheader',
                     names=('reqheader', 'requestheader')),
        GroupedField('responseheader', label='Response Headers',
                     rolename='mailheader',
                     names=('resheader', 'responseheader')),
        GroupedField('statuscode', label='Status Codes',
                     rolename='statuscode',
                     names=('statuscode', 'status', 'code'))
    ]

    method = NotImplemented

    def handle_signature(self, sig, signode):
        method = self.method.upper() + ' '
        signode += addnodes.desc_name(method, method)
        offset = 0
        for match in http_sig_param_re.finditer(sig):
            path = sig[offset:match.start()]
            signode += addnodes.desc_name(path, path)
            params = addnodes.desc_parameterlist()
            typ = match.group('type')
            if typ:
                typ = typ + ': '
                params += addnodes.desc_annotation(typ, typ)
            name = match.group('name')
            params += addnodes.desc_parameter(name, name)
            signode += params
            offset = match.end()
        if offset < len(sig):
            path = sig[offset:len(sig)]
            signode += addnodes.desc_name(path, path)
        fullname = self.method.upper() + ' ' + path
        signode['method'] = self.method
        signode['path'] = sig
        signode['fullname'] = fullname
        return (fullname, self.method, sig)

    def needs_arglist(self):
        return False

    def add_target_and_index(self, name_cls, sig, signode):
        signode['ids'].append(http_resource_anchor(*name_cls[1:]))
        self.env.domaindata['http'][self.method][sig] = (self.env.docname, '')

    def get_index_text(self, modname, name):
        return ''


class HTTPOptions(HTTPResource):

    method = 'options'


class HTTPHead(HTTPResource):

    method = 'head'


class HTTPPatch(HTTPResource):

    method = 'patch'


class HTTPPost(HTTPResource):

    method = 'post'


class HTTPGet(HTTPResource):

    method = 'get'


class HTTPPut(HTTPResource):

    method = 'put'


class HTTPDelete(HTTPResource):

    method = 'delete'


class HTTPTrace(HTTPResource):

    method = 'trace'


def http_statuscode_role(name, rawtext, text, lineno, inliner,
                         options={}, content=[]):
    if text.isdigit():
        code = int(text)
        try:
            status = HTTP_STATUS_CODES[code]
        except KeyError:
            msg = inliner.reporter.error('%d is invalid HTTP status code'
                                         % code, lineno=lineno)
            prb = inliner.problematic(rawtext, rawtext, msg)
            return [prb], [msg]
    else:
        try:
            code, status = re.split(r'\s', text.strip(), 1)
            code = int(code)
        except ValueError:
            msg = inliner.reporter.error(
                'HTTP status code must be an integer (e.g. `200`) or '
                'start with an integer (e.g. `200 OK`); %r is invalid' %
                text,
                line=lineno
            )
            prb = inliner.problematic(rawtext, rawtext, msg)
            return [prb], [msg]
    nodes.reference(rawtext)
    if code == 226:
        url = 'http://www.ietf.org/rfc/rfc3229.txt'
    if code == 418:
        url = 'http://www.ietf.org/rfc/rfc2324.txt'
    if code == 449:
        url = 'http://msdn.microsoft.com/en-us/library' \
              '/dd891478(v=prot.10).aspx'
    elif code in HTTP_STATUS_CODES:
        url = 'http://www.w3.org/Protocols/rfc2616/rfc2616-sec10.html' \
              '#sec10.' + ('%d.%d' % (code // 100, 1 + code % 100))
    else:
        url = ''
    set_classes(options)
    node = nodes.reference(rawtext, '%d %s' % (code, status),
                           refuri=url, **options)
    return [node], []


def http_method_role(name, rawtext, text, lineno, inliner,
                     options={}, content=[]):
    method = str(text).lower()
    if method not in DOCREFS:
        msg = inliner.reporter.error('%s is not valid HTTP method' % method,
                                     lineno=lineno)
        prb = inliner.problematic(rawtext, rawtext, msg)
        return [prb], [msg]
    url = str(DOCREFS[method])
    node = nodes.reference(rawtext, method.upper(), refuri=url, **options)
    return [node], []


class HTTPXRefRole(XRefRole):

    def __init__(self, method, **kwargs):
        XRefRole.__init__(self, **kwargs)
        self.method = method

    def process_link(self, env, refnode, has_explicit_title, title, target):
        if not target.startswith('/'):
            pass
        if not has_explicit_title:
            title = self.method.upper() + ' ' + title
        return title, target


class HTTPIndex(Index):

    name = 'routingtable'
    localname = 'HTTP Routing Table'
    shortname = 'routing table'

    def __init__(self, *args, **kwargs):
        super(HTTPIndex, self).__init__(*args, **kwargs)

        self.ignore = [[l for l in x.split('/') if l]
            for x in self.domain.env.config['http_index_ignore_prefixes']]
        self.ignore.sort(key=lambda x: -len(x))

    def grouping_prefix(self, path):
        letters = [x for x in path.split('/') if x]
        for prefix in self.ignore:
            if letters[:len(prefix)] == prefix:
                return '/' + '/'.join(letters[:len(prefix) + 1])
        return '/%s' % (letters[0] if letters else '',)

    def generate(self, docnames=None):
        content = {}
        items = ((method, path, info)
            for method, routes in self.domain.routes.items()
            for path, info in routes.items())
        items = sorted(items, key=lambda item: item[1])
        for method, path, info in items:
            entries = content.setdefault(self.grouping_prefix(path), [])
            entries.append([
                method.upper() + ' ' + path, 0, info[0],
                http_resource_anchor(method, path), '', '', info[1]
            ])
        content = sorted(content.items(), key=lambda k: k[0])
        return (content, True)


class HTTPDomain(Domain):
    """HTTP domain."""

    name = 'http'
    label = 'HTTP'

    object_types = {
        'options': ObjType('options', 'options', 'obj'),
        'head': ObjType('head', 'head', 'obj'),
        'post': ObjType('post', 'post', 'obj'),
        'get': ObjType('get', 'get', 'obj'),
        'put': ObjType('put', 'put', 'obj'),
        'patch': ObjType('patch', 'patch', 'obj'),
        'delete': ObjType('delete', 'delete', 'obj'),
        'trace': ObjType('trace', 'trace', 'obj')
    }

    directives = {
        'options': HTTPOptions,
        'head': HTTPHead,
        'post': HTTPPost,
        'get': HTTPGet,
        'put': HTTPPut,
        'patch': HTTPPatch,
        'delete': HTTPDelete,
        'trace': HTTPTrace
    }

    roles = {
        'options': HTTPXRefRole('options'),
        'head': HTTPXRefRole('head'),
        'post': HTTPXRefRole('post'),
        'get': HTTPXRefRole('get'),
        'put': HTTPXRefRole('put'),
        'patch': HTTPXRefRole('patch'),
        'delete': HTTPXRefRole('delete'),
        'trace': HTTPXRefRole('trace'),
        'statuscode': http_statuscode_role,
        'method': http_method_role
    }

    initial_data = {
        'options': {}, # path: (docname, synopsis)
        'head': {},
        'post': {},
        'get': {},
        'put': {},
        'patch': {},
        'delete': {},
        'trace': {}
    }

    # indices = [HTTPIndex]
    indices = []

    @property
    def routes(self):
        return dict((key, self.data[key]) for key in self.object_types)

    def clear_doc(self, docname):
        for typ, routes in self.routes.items():
            for path, info in list(routes.items()):
                if info[0] == docname:
                    del routes[path]

    def resolve_xref(self, env, fromdocname, builder, typ, target,
                     node, contnode):
        try:
            info = self.data[str(typ)][target]
        except KeyError:
            return
        else:
            anchor = http_resource_anchor(typ, target)
            title = typ.upper() + ' ' + target
            return make_refnode(builder, fromdocname, info[0], anchor,
                                contnode, title)

    def get_objects(self):
        for method, routes in self.routes.items():
            for path, info in routes.items():
                anchor = http_resource_anchor(method, path)
                yield (path, path, method, info[0], anchor, 1)


class HTTPLexer(RegexLexer):
    """Lexer for HTTP sessions."""

    name = 'HTTP'
    aliases = ['http']

    flags = re.DOTALL

    def header_callback(self, match):
        if match.group(1).lower() == 'content-type':
            content_type = match.group(5).strip()
            if ';' in content_type:
                content_type = content_type[:content_type.find(';')].strip()
            self.content_type = content_type
        yield match.start(1), Name.Attribute, match.group(1)
        yield match.start(2), Text, match.group(2)
        yield match.start(3), Operator, match.group(3)
        yield match.start(4), Text, match.group(4)
        yield match.start(5), Literal, match.group(5)
        yield match.start(6), Text, match.group(6)

    def continuous_header_callback(self, match):
        yield match.start(1), Text, match.group(1)
        yield match.start(2), Literal, match.group(2)
        yield match.start(3), Text, match.group(3)

    def content_callback(self, match):
        content_type = getattr(self, 'content_type', None)
        content = match.group()
        offset = match.start()
        if content_type:
            from pygments.lexers import get_lexer_for_mimetype
            try:
                lexer = get_lexer_for_mimetype(content_type)
            except ClassNotFound:
                pass
            else:
                for idx, token, value in lexer.get_tokens_unprocessed(content):
                    yield offset + idx, token, value
                return
        yield offset, Text, content

    tokens = {
        'root': [
            (r'(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS|TRACE)( +)([^ ]+)( +)'
             r'(HTTPS?)(/)(1\.[01])(\r?\n|$)',
             bygroups(Name.Function, Text, Name.Namespace, Text,
                      Keyword.Reserved, Operator, Number, Text),
             'headers'),
            (r'(HTTPS?)(/)(1\.[01])( +)(\d{3})( +)([^\r\n]+)(\r?\n|$)',
             bygroups(Keyword.Reserved, Operator, Number, Text, Number,
                      Text, Name.Exception, Text),
             'headers'),
        ],
        'headers': [
            (r'([^\s:]+)( *)(:)( *)([^\r\n]+)(\r?\n|$)', header_callback),
            (r'([\t ]+)([^\r\n]+)(\r?\n|$)', continuous_header_callback),
            (r'\r?\n', Text, 'content')
        ],
        'content': [
            (r'.+', content_callback)
        ]
    }


def setup(app):
    app.add_domain(HTTPDomain)
    try:
        get_lexer_by_name('http')
    except ClassNotFound:
        app.add_lexer('http', HTTPLexer())
    app.add_config_value('http_index_ignore_prefixes', [], None)

