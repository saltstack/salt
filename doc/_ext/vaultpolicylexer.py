from pygments.lexer import bygroups, inherit
from pygments.lexers.configs import TerraformLexer
from pygments.token import Keyword, Name, Punctuation, Whitespace


class VaultPolicyLexer(TerraformLexer):
    aliases = ["vaultpolicy"]
    filenames = ["*.hcl"]
    mimetypes = ["application/x-hcl-policy"]

    tokens = {
        "basic": [
            inherit,
            (
                r"(path)(\s+)(\".*\")(\s+)(\{)",
                bygroups(
                    Keyword.Reserved, Whitespace, Name.Variable, Whitespace, Punctuation
                ),
            ),
        ],
    }


def setup(app):
    app.add_lexer("vaultpolicy", VaultPolicyLexer)
    return {"parallel_read_safe": True}
