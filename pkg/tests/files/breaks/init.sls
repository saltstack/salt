#!py
"""."""


def run():
    """."""
    return {
        "file_foobar": {
            "file.managed": [
                {
                    "name": "/foobar"
                },
                {
                    "template": "jinja"
                },
                {
                    "context": {
                        "foobar": "baz",
                    }
                },
                {
                    "source": "salt://breaks/foobar.jinja",
                }
            ]
        }
    }
