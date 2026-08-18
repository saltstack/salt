"""
Common functions for working with deb packages
"""


def combine_comments(comments):
    """
    Given a list of comments, or a comment submitted as a string, return a
    single line of text containing all of the comments.
    """
    if isinstance(comments, list):
        comments = [c if isinstance(c, str) else str(c) for c in comments]
    else:
        if not isinstance(comments, str):
            comments = [str(comments)]
        else:
            comments = [comments]
    return " ".join(comments).strip()


def strip_uri(repo):
    """
    Remove the trailing slash from the URI in a repo definition
    """
    splits = repo.split()
    for idx, val in enumerate(splits):
        if any(val.startswith(x) for x in ("http://", "https://", "ftp://")):
            splits[idx] = val.rstrip("/")
    return " ".join(splits)
