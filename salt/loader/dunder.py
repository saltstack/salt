"""
Salt dunders.
"""
import salt.loader.context

loader_context = salt.loader.context.LoaderContext()


__file_client__ = loader_context.named_context("__file_client__", default=None)
