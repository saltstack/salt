"""
Keep HTML anchors on ``:noindex:``'d httpdomain directives.

sphinxcontrib-httpdomain's ``add_target_and_index`` intentionally splits its
two jobs: it always appends the ``#<method>--<path>`` anchor to the signature
node, and only gates the global route *registration* behind ``:noindex:``.
Sphinx's ``ObjectDescription.run`` however skips the whole method when
``noindex`` is set, so the anchor (and its permalink) is lost along with the
index entry. Anchors are per-page HTML ids and cannot collide across pages,
so restoring them is safe; only the global registration can produce the
parallel-build duplicate-route warnings.

Hide the option from Sphinx's outer gate and re-present it to httpdomain's
inner gate, so ``:noindex:`` means what httpdomain meant it to mean: no index
entry, anchor kept.
"""

from sphinxcontrib.httpdomain import HTTPDomain


def _make_anchored(cls):
    class AnchoredHTTPResource(cls):
        def run(self):
            self._salt_noindex = "noindex" in self.options
            self.options.pop("noindex", None)
            return super().run()

        def add_target_and_index(self, name_cls, sig, signode):
            if self._salt_noindex:
                self.options["noindex"] = None
            try:
                super().add_target_and_index(name_cls, sig, signode)
            finally:
                if self._salt_noindex:
                    self.options.pop("noindex", None)

    AnchoredHTTPResource.__name__ = f"Anchored{cls.__name__}"
    return AnchoredHTTPResource


def setup(app):
    app.setup_extension("sphinxcontrib.httpdomain")
    for name, cls in list(HTTPDomain.directives.items()):
        app.add_directive_to_domain("http", name, _make_anchored(cls), override=True)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
