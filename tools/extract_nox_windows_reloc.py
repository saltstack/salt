#!/usr/bin/env python3
"""
Extract nox.windows.amd64.tar.gz into REPO_ROOT, remapping CI symlink targets
(D:\\a\\salt\\salt, //?/D:/...) to the local repo so Windows tar/git tar does not fail.

Then apply the same pyvenv.cfg + broken-symlink repair as noxfile decompress-dependencies.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import sys
import tarfile


def _ci_path_prefixes() -> list[str]:
    # Longest first for correct matching (GitHub Actions checkout path)
    bases = [
        r"\\?\D:\a\salt\salt",
        "//?/D:/a/salt/salt",
        "D:\\a\\salt\\salt",
        "D:/a/salt/salt",
        r"D:\a\salt\salt",
    ]
    return sorted(set(bases), key=len, reverse=True)


def remap_link(linkname: str, repo: pathlib.Path) -> str:
    for p in _ci_path_prefixes():
        if linkname.startswith(p):
            rest = linkname[len(p) :].lstrip("/\\")
            return os.path.normpath(str(repo / rest.replace("/", os.sep)))
    return linkname


def extract_reloc(repo: pathlib.Path) -> None:
    archive = repo / "nox.windows.amd64.tar.gz"
    if not archive.is_file():
        raise SystemExit(f"Missing {archive}")
    nox_dir = repo / ".nox"
    if nox_dir.exists():
        shutil.rmtree(nox_dir)

    extract_kw: dict = {}
    if sys.version_info >= (3, 12):
        extract_kw["filter"] = "fully_trusted"

    with tarfile.open(archive, "r:gz") as tf:
        for m in tf.getmembers():
            if m.issym() or m.islnk():
                m.linkname = remap_link(m.linkname, repo)
            tf.extract(m, path=str(repo), **extract_kw)


def fix_nox_windows(repo: pathlib.Path) -> None:
    scripts_dir_name = "Scripts"
    pyexecutable = "python.exe"
    platform = "windows"
    for entry in os.scandir(repo / ".nox"):
        if not entry.is_dir():
            continue
        dirname = entry.path
        scan_path = pathlib.Path(dirname) / scripts_dir_name

        config = pathlib.Path(dirname) / "pyvenv.cfg"
        values: dict[str, str] = {}
        if config.exists():
            with open(config, encoding="utf-8") as fp:
                for line in fp:
                    key, val = (_.strip() for _ in line.split("=", 1))
                    values[key] = val
            values["home"] = str(
                repo.joinpath("artifacts", "salt", scripts_dir_name)
            )
            values["base-prefix"] = str(repo.joinpath("artifacts", "salt"))
            values["base-exec-prefix"] = str(repo.joinpath("artifacts", "salt"))
            values["base-executable"] = str(
                repo.joinpath("artifacts", "salt", scripts_dir_name, pyexecutable)
            )
            with open(config, "w", encoding="utf-8") as fp:
                for key in values:
                    fp.write(f"{key} = {values[key]}\n")
        if not scan_path.is_dir():
            continue
        script_paths = {str(p): p for p in os.scandir(scan_path)}
        for key in sorted(script_paths):
            path = script_paths[key]
            if path.is_symlink():
                broken_link = pathlib.Path(path)
                resolved_link = os.readlink(path)
                if not os.path.isabs(resolved_link):
                    resolved_link = os.path.join(scan_path, resolved_link)
                prefix_check = False
                if platform == "windows":
                    prefix_check = resolved_link.startswith("\\\\?")
                if not os.path.exists(resolved_link) or prefix_check:
                    resolved_link_suffix = resolved_link.split(
                        f"artifacts{os.sep}salt{os.sep}"
                    )[-1]
                    fixed_link = repo.joinpath(
                        "artifacts", "salt", resolved_link_suffix
                    )
                    broken_link.unlink()
                    broken_link.symlink_to(fixed_link)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} <repo_root>")
    repo = pathlib.Path(sys.argv[1]).resolve()
    extract_reloc(repo)
    fix_nox_windows(repo)
    print("OK:", repo / ".nox")


if __name__ == "__main__":
    main()
