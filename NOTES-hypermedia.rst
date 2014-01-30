https://speakerdeck.com/owolf/turning-passive-apis-into-active-apis

URI templates to cut down on repetition::

    {
        "_links": {
            "items": {"href": "/action/package_show?{id}" }
        },
        "result": [
            {"id": "someidhere-91911"},
            {"id": "otheridhere-38344"}
        ],
        "help": "Return a list of the names of the site's data packages"
    }

Adding entries::

    {
        "_links": {
            "items": {"href": "/action/package_show?{id}" },
            "create": {
                "href": "/action/package_create"
                "hints": {
                    "allow": ["POST"],
                    "representations": ["application/json"]
                }
            }
        },
        "result": [
            {"id": "someidhere-91911"},
            {"id": "otheridhere-38344"}
        ],
        "help": "Return a list of the names of the site's data packages"
    }
