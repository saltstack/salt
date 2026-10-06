import salt.utils.pkg.deb
from salt.utils.pkg.deb import SourceEntry


def test__get_opts():
    tests = [
        {
            "oneline": "deb [signed-by=/etc/apt/keyrings/example.key arch=amd64] https://example.com/pub/repos/apt xenial main",
            "result": {
                "signedby": {
                    "full": "signed-by=/etc/apt/keyrings/example.key",
                    "value": "/etc/apt/keyrings/example.key",
                },
                "arch": {"full": "arch=amd64", "value": ["amd64"]},
            },
        },
        {
            "oneline": "deb [arch=amd64 signed-by=/etc/apt/keyrings/example.key]  https://example.com/pub/repos/apt xenial main",
            "result": {
                "arch": {"full": "arch=amd64", "value": ["amd64"]},
                "signedby": {
                    "full": "signed-by=/etc/apt/keyrings/example.key",
                    "value": "/etc/apt/keyrings/example.key",
                },
            },
        },
        {
            "oneline": "deb [arch=amd64]  https://example.com/pub/repos/apt xenial main",
            "result": {
                "arch": {"full": "arch=amd64", "value": ["amd64"]},
            },
        },
        {
            "oneline": "deb [signed-by=/etc/apt/keyrings/example.key arch=arm64] https://example.com/pub/repos/apt xenial main",
            "result": {
                "signedby": {
                    "full": "signed-by=/etc/apt/keyrings/example.key",
                    "value": "/etc/apt/keyrings/example.key",
                },
                "arch": {"full": "arch=arm64", "value": ["arm64"]},
            },
        },
    ]

    for test in tests:
        ret = salt.utils.pkg.deb._get_opts(test["oneline"])
        assert ret == test["result"]


def test_SourceEntry_init():
    source = SourceEntry(
        "deb [arch=amd64 signed-by=/etc/apt/keyrings/example.key] https://example.com/pub/repos/apt xenial main",
        file="/tmp/test.list",
    )
    assert source.invalid is False
    assert source.comps == ["main"]
    assert source.comment == ""
    assert source.dist == "xenial"
    assert source.type == "deb"
    assert source.uri == "https://example.com/pub/repos/apt"
    assert source.architectures == ["amd64"]
    assert source.signedby == "/etc/apt/keyrings/example.key"
    assert source.file == "/tmp/test.list"


def test_SourceEntry_repo_line():

    lines = [
        "deb [arch=amd64 signed-by=/etc/apt/keyrings/example.key] https://example.com/pub/repos/apt xenial main\n",
        "deb [signed-by=/etc/apt/keyrings/example.key] https://example.com/pub/repos/apt xenial main\n",
        "deb [signed-by=/etc/apt/keyrings/example.key arch=amd64,x86_64] https://example.com/pub/repos/apt xenial main\n",
        "deb [signed-by=/etc/apt/keyrings/example.key arch=arm64] https://example.com/pub/repos/apt xenial main\n",
    ]
    for line in lines:
        source = SourceEntry(line, file="/tmp/test.list")
        assert source.invalid is False
        assert source.repo_line() == line

    lines = [
        (
            "deb [arch=amd64 signed-by=/etc/apt/keyrings/example.key] https://example.com/pub/repos/apt xenial main\n",
            "deb [arch=x86_64 signed-by=/etc/apt/keyrings/example.key] https://example.com/pub/repos/apt xenial main\n",
            "deb [arch=arm64 signed-by=/etc/apt/keyrings/example.key] https://example.com/pub/repos/apt xenial main\n",
        ),
        (
            "deb [signed-by=/etc/apt/keyrings/example.key] https://example.com/pub/repos/apt xenial main\n",
            "deb [signed-by=/etc/apt/keyrings/example.key arch=x86_64] https://example.com/pub/repos/apt xenial main\n",
            "deb [signed-by=/etc/apt/keyrings/example.key arch=arm64] https://example.com/pub/repos/apt xenial main\n",
        ),
        (
            "deb [signed-by=/etc/apt/keyrings/example.key arch=amd64,x86_64] https://example.com/pub/repos/apt xenial main\n",
            "deb [signed-by=/etc/apt/keyrings/example.key arch=x86_64] https://example.com/pub/repos/apt xenial main\n",
            "deb [signed-by=/etc/apt/keyrings/example.key arch=arm64] https://example.com/pub/repos/apt xenial main\n",
        ),
        (
            "deb [signed-by=/etc/apt/keyrings/example.key arch=amd64,x86_64] https://example.com/pub/repos/apt xenial main\n",
            "deb [signed-by=/etc/apt/keyrings/example.key arch=x86_64] https://example.com/pub/repos/apt xenial main\n",
            "deb [signed-by=/etc/apt/keyrings/example.key arch=arm64] https://example.com/pub/repos/apt xenial main\n",
        ),
    ]
    for line in lines:
        line_key, line_value1, line_value2 = line
        source = SourceEntry(line_key, file="/tmp/test.list")
        source.architectures = ["x86_64"]
        assert source.invalid is False
        assert source.repo_line() == line_value1
        assert source.invalid is False
        source.architectures = ["arm64"]
        assert source.invalid is False
        assert source.repo_line() == line_value2
        assert source.invalid is False
