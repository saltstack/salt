"""
salt._logging.filters
~~~~~~~~~~~~~~~~~~~~~

Logging ``logging.Filter`` implementations attached to Salt's logging
handlers.  Each filter mutates ``LogRecord`` instances before they are
formatted and emitted; this is the preferred extension point for cross
cutting output-boundary concerns such as redacting pillar values.
"""
