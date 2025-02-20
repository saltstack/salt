"""
Salt dunders.
"""

import salt.loader.context

loader_context = salt.loader.context.LoaderContext()


__file_client__ = loader_context.named_context("__file_client__", default=None)
__opts__ = loader_context.named_context("__opts__")
__context__ = loader_context.named_context("__context__")
__pillar__ = loader_context.named_context("__pillar__")
__grains__ = loader_context.named_context("__grains__")
