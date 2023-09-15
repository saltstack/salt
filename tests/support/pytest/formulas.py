import functools
import pathlib
import shutil
import zipfile

import attr
import pytest


@attr.s(slots=True, frozen=True)
class SaltStackFormula:
    """
    Class representing a saltstack formula.
    """

    name: str = attr.ib()
    tag: str = attr.ib()
    tmp_path: pathlib.Path = attr.ib()
    state_tree_path: pathlib.Path = attr.ib()
    url: str = attr.ib()

    @url.default
    def _default_url(self):
        return f"https://github.com/saltstack-formulas/{self.name}/archive/refs/tags/v{self.tag}.zip"

    def __enter__(self):
        target_path = self.state_tree_path / f"{self.name}-{self.tag}"
        if not target_path.exists():
            zipfile_path = pytest.helpers.download_file(
                self.url, self.tmp_path / self.url.split("/")[-1]
            )
            with zipfile.ZipFile(zipfile_path) as zip_obj:
                zip_obj.extractall(self.tmp_path)
            shutil.move(self.tmp_path / f"{self.name}-{self.tag}", target_path)
        return self

    def __exit__(self, *_):
        pass

    @classmethod
    def with_default_paths(cls, tmp_path, state_tree_path):
        return functools.partial(
            cls, tmp_path=tmp_path, state_tree_path=state_tree_path
        )
