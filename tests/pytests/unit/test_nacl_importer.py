import pytest

from salt import NaclImporter


@pytest.mark.parametrize("fullname", ["nacl", "nacl.signing"])
def test_find_spec_accepts_nacl(fullname, monkeypatch):
    monkeypatch.setattr(NaclImporter, "loading", False)
    importer = NaclImporter()

    spec = importer.find_spec(fullname)

    assert spec is not None
    assert spec.name == fullname
    assert spec.loader is importer
    assert NaclImporter.loading is True


def test_find_spec_declines_unrelated_module(monkeypatch):
    monkeypatch.setattr(NaclImporter, "loading", False)
    importer = NaclImporter()

    assert importer.find_spec("json") is None
    assert NaclImporter.loading is False


def test_find_spec_declines_while_loading(monkeypatch):
    monkeypatch.setattr(NaclImporter, "loading", True)
    importer = NaclImporter()

    assert importer.find_spec("nacl.signing") is None
    assert NaclImporter.loading is True
