"""
Literature
- http://www.kuwata-lab.com/kwalify/ruby/users-guide.02.html
- http://yaml.org/type/value.html
- http://www.kuwata-lab.com/kwalify/ruby/users-guide.02.html
"""

from yaml import Dumper, dump_all
from collections import defaultdict

class AnchoredDumper(Dumper):
    """
    Dumps an object into YAML with anchors for Mappings and Sequences.

    If default_flow_style is False, only nested mappings and sequences will be
    anchored. Otherwise it will be applicated to the whole document.

    anchors
      composed by the top document name + __ + mapping key or sequence indice

    For example this data:

    .. code:: python

      top_anchor = "MYANCHOR"
      include_document = True
      data = {
          "foo": {
              "first": True,
              "second": False,
          },
          "bar": [ 1, 2, { "hello": "motto" } ]
      }

    will be serialized as:

    .. code:: yaml

      ---
      foo: &MYANCHOR__foo {
        first: true,
        second: false
      },
      bar: &MYANCHOR__bar [
        1,
        2,
        &MYANCHOR__bar__2 {
          hello: motto
        }
      ]

    by convenience document will not be anchored, but you can activate this
    by setting the parameter ``include_document`` to ``True``:

    .. code:: yaml

      ---
      &MYANCHOR {
        foo: &MYANCHOR__foo {
          first: true,
          second: false
        },
        bar: &MYANCHOR__bar [
          1,
          2,
          &MYANCHOR__bar__2 {
            hello: motto
          }
        ]
      }
    """
    def __init__(self, *args, **kwargs):
        self.top_anchor = kwargs.pop('top_anchor', "document").replace('.', '_')
        self.include_document = kwargs.pop('include_document', False)
        super(AnchoredDumper, self).__init__(*args, **kwargs)
        self.anchors = defaultdict(lambda: None)

    def serialize(self, node):
        def anchorize(*parts):
            return '__'.join(str(part).replace('.', '_') for part in parts)


        def prepare_anchors(node, anchor, enable=True):
            if node.tag in ('tag:yaml.org,2002:map', 'tag:yaml.org,2002:omap'):
                if enable:
                    self.anchors[node] = anchor
                    node.flow_style = True
                for key, value in node.value:
                    prepare_anchors(value, anchorize(anchor, key.value))
            elif node.tag in ('tag:yaml.org,2002:seq',):
                if enable:
                    self.anchors[node] = anchor
                    node.flow_style = True
                for i, value in enumerate(node.value):
                    prepare_anchors(value, anchorize(anchor, i))
        prepare_anchors(node, self.top_anchor, self.include_document)

        response = super(AnchoredDumper, self).serialize(node)
        self.anchors = defaultdict(lambda: None)
        return response

def anchored_dump_all(documents, stream=None, top_anchor=None, include_document=False, **kwds):
    def local_dumper(*args, **kwargs):
        kwargs['top_anchor'] = top_anchor or "document"
        kwargs['include_document'] = include_document
        return AnchoredDumper(*args, **kwargs)

    return dump_all(documents, stream, Dumper=local_dumper, **kwds)


def anchored_dump(data, stream=None, top_anchor=None, **kwds):
    return anchored_dump_all([data], stream, top_anchor, **kwds)
