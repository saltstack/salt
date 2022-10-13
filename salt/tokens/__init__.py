"""
    salt.tokens
    ~~~~~~~~~~~~

    This module implements all the token stores used by salt during eauth authentication.
    Each store must implement the following methods:

    :mk_token: function to mint a new unique token and store it

    :get_token: function to get data of a given token if it exists

    :rm_token: remove the given token from storage

    :list_tokens: list all tokens in storage

"""
