# -*- coding: utf-8 -*-

from invoke import Collection  # pylint: disable=3rd-party-module-not-gated
from . import docs

ns = Collection()
docs = Collection.from_module(docs, name="docs")
ns.add_collection(docs, name="docs")
