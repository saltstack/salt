import contextlib
import copy
import shutil
import stat
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def symlink_scenario_1(state_tree):
    # Create directory structure
    dir_name = "symlink_scenario_1"
    source_dir = state_tree / dir_name
    if not source_dir.is_dir():
        source_dir.mkdir()
    source_file = source_dir / "source_file.txt"
    source_file.write_text("This is the source file...")
    symlink_file = source_dir / "symlink"
    symlink_file.symlink_to(source_file)
    yield dir_name


@pytest.fixture(scope="module")
def symlink_scenario_2(state_tree):
    # Create directory structure
    dir_name = "symlink_scenario_2"
    source_dir = state_tree / dir_name / "test"
    if not source_dir.is_dir():
        source_dir.mkdir(parents=True)
    test1 = source_dir / "test1"
    test2 = source_dir / "test2"
    test3 = source_dir / "test3"
    test_link = source_dir / "test"
    test1.touch()
    test2.touch()
    test3.touch()
    test_link.symlink_to(test3)
    yield dir_name


@pytest.fixture(scope="module")
def symlink_scenario_3(state_tree):
    # Create directory structure
    dir_name = "symlink_scenario_3"
    source_dir = state_tree / dir_name
    if not source_dir.is_dir():
        source_dir.mkdir(parents=True)
    # Create a file with the same name but is not a symlink
    source_file = source_dir / "not_a_symlink" / "symlink"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("This is the source file...")
    # Create other fluff files
    just_a_file = source_dir / "just_a_file.txt"
    just_a_file.touch()
    dummy_file = source_dir / "notasymlink"
    dummy_file.touch()
    # Create symlink to source with the same name
    symlink_file = source_dir / "symlink"
    symlink_file.symlink_to(source_file)
    yield dir_name


@pytest.mark.parametrize("test", (False, True))
def test_recurse(file, tmp_path, grail, test):
    """
    file.recurse
    """
    name = tmp_path / "grail-dest-dir"
    ret = file.recurse(name=str(name), source="salt://grail", test=test)
    if test is False:
        assert ret.result is True

        scene_36_src = grail / "36" / "scene"
        scene_36_dst = name / "36" / "scene"
        assert scene_36_dst.is_file()
        assert scene_36_src.read_text() == scene_36_dst.read_text()
    else:
        assert ret.result is None

        scene_36_dst = name / "36" / "scene"
        assert scene_36_dst.is_file() is False
        assert name.exists() is False


@pytest.mark.parametrize("saltenv_param", ("__env__", "saltenv"))
def test_recurse_specific_env(file, tmp_path, holy, saltenv_param):
    """
    file.recurse passing __env__
    """
    name = tmp_path / "holy-dest-dir"
    kwargs = {saltenv_param: "prod"}
    ret = file.recurse(name=str(name), source="salt://holy", **kwargs)
    assert ret.result is True

    scene_32_src = holy / "32" / "scene"
    scene_32_dst = name / "32" / "scene"
    assert scene_32_dst.is_file()
    assert scene_32_src.read_text() == scene_32_dst.read_text()


def test_recurse_specific_env_in_url(file, tmp_path, holy):
    """
    file.recurse passing __env__
    """
    name = tmp_path / "holy-dest-dir"
    ret = file.recurse(name=str(name), source="salt://holy?saltenv=prod")
    assert ret.result is True

    scene_32_src = holy / "32" / "scene"
    scene_32_dst = name / "32" / "scene"
    assert scene_32_dst.is_file()
    assert scene_32_src.read_text() == scene_32_dst.read_text()


@pytest.mark.usefixtures("holy")
@pytest.mark.parametrize("saltenv_param", ("__env__", "saltenv"))
def test_test_recurse_specific_env(file, tmp_path, saltenv_param):
    """
    file.recurse passing __env__
    """
    name = tmp_path / "holy-dest-dir"
    kwargs = {saltenv_param: "prod"}
    ret = file.recurse(name=str(name), source="salt://holy", test=True, **kwargs)
    assert ret.result is None

    scene_32_dst = name / "32" / "scene"
    assert scene_32_dst.is_file() is False
    assert name.exists() is False


def test_recurse_template(file, tmp_path, grail):
    """
    file.recurse with jinja template enabled
    """
    name = tmp_path / "dest-dir"
    template_string = "TEMPLATE TEST STRING"
    ret = file.recurse(
        name=str(name),
        source="salt://grail",
        template="jinja",
        defaults={"spam": template_string},
    )
    assert ret.result is True

    scene_src = grail / "scene33"
    scene_dst = name / "scene33"
    assert scene_dst.is_file()
    assert scene_src.read_text() != scene_dst.read_text()
    assert template_string in scene_dst.read_text()


@pytest.mark.usefixtures("grail")
def test_recurse_clean(file, tmp_path):
    """
    file.recurse with clean=True
    """
    name = tmp_path / "dest-dir"
    name.mkdir()
    strayfile = name / "strayfile"
    strayfile.write_text("")
    scene_33_dst = name / "scene33"
    scene_36_dst = name / "36"

    # Corner cases: replacing file with a directory and vice versa
    # <name>/36 is supposed to be a directory.
    # Create a file with the same name to see if clean handles it
    scene_36_dst.write_text("")
    # <name>/scene33 is supposed to be a file.
    # Create a directory with the same name to see if clean handles it
    scene_33_dst.mkdir()
    ret = file.recurse(name=str(name), source="salt://grail", clean=True)
    assert ret.result is True
    assert strayfile.exists() is False
    assert scene_33_dst.is_dir() is False
    assert scene_33_dst.is_file()
    assert scene_36_dst.is_file() is False
    assert scene_36_dst.is_dir()
    assert scene_36_dst.joinpath("scene").is_file() is True


@pytest.mark.usefixtures("holy")
def test_recurse_clean_specific_env(file, tmp_path):
    """
    file.recurse with clean=True and saltenv=prod
    """
    name = tmp_path / "dest-dir"
    name.mkdir()
    strayfile = name / "strayfile"
    strayfile.write_text("")
    scene_34_dst = name / "scene34"
    scene_32_dst = name / "32"

    # Corner cases: replacing file with a directory and vice versa
    # <name>/32 is supposed to be a directory.
    # Create a file with the same name to see if clean handles it
    scene_32_dst.write_text("")
    # <name>/scene34 is supposed to be a file.
    # Create a directory with the same name to see if clean handles it
    scene_34_dst.mkdir()
    ret = file.recurse(name=str(name), source="salt://holy", clean=True, saltenv="prod")
    assert ret.result is True
    assert strayfile.exists() is False
    assert scene_34_dst.is_dir() is False
    assert scene_34_dst.is_file()
    assert scene_32_dst.is_file() is False
    assert scene_32_dst.is_dir()
    assert scene_32_dst.joinpath("scene").is_file() is True


@contextlib.contextmanager
def create_file_tree(base, tree):
    """
    Helper to quickly create trees of directories, files and symlinks
    inside a base directory.
    """
    temp_files = []
    symlinks = {}
    empty_dirs = []

    def _create_tmp_files(tree, prefix):
        for name, val in tree.items():
            if isinstance(val, dict):
                if not val:
                    empty_dirs.append(base / prefix / name)
                    continue
                _create_tmp_files(val, prefix + f"/{name}")
                continue
            if isinstance(val, tuple):
                symlinks[base / prefix / name] = val[0]
                continue
            temp_files.append(pytest.helpers.temp_file(name, val, base / prefix))

    for first_level_name, first_level_contents in tree.items():
        _create_tmp_files(first_level_contents, first_level_name)

    with contextlib.ExitStack() as stack:
        for file in temp_files:
            stack.enter_context(file)
        try:
            created_dirs = []
            for empty_dir in empty_dirs:
                for par in empty_dir.parents[::-1]:
                    if not par.exists():
                        created_dirs.append(par)
                        break
                empty_dir.mkdir(parents=True)
            for symlink, target in symlinks.items():
                for par in symlink.parents[::-1]:
                    if not par.exists():
                        created_dirs.append(par)
                        break
                symlink.parent.mkdir(parents=True, exist_ok=True)
                is_dir = target.endswith("/")
                symlink.symlink_to(Path(target.rstrip("/")), target_is_directory=is_dir)
                if is_dir:
                    assert symlink.is_symlink()
                    assert symlink.is_dir()
            yield
        finally:
            for symlink in symlinks:
                symlink.unlink(missing_ok=True)
            for created_dir in created_dirs + empty_dirs:
                shutil.rmtree(created_dir, ignore_errors=True)


@pytest.fixture
def _recurse_merge_dirs(state_tree, state_tree_prod):
    tree_base = {
        "file_from_base": "base",
        "overridden_file": "foo",
        "common": {
            "file_from_base": "base",
            "overridden_file": "foo",
        },
        "base": {
            "present": "",
        },
        "empty": {
            "in_base": {},
            "common": {},
            "override": {},
            "override_file": "",
            "nested_in_base_only": {
                "worked": {},
                "nonempty": {
                    "file": "",
                },
            },
        },
        "deeply": "not_rendered",
        "file_overridden_by_dir": "file",
        "dir_overridden_by_file": {
            "file_in_dir": "",
        },
        "symlinked_dir": ("symlink_target_dir/",),
        "symlinked_file": ("symlink_target_file",),
        "symlink_target_dir": {
            "file_in_symlink_target": "",
        },
        "symlink_target_file": "",
        "symlink_dir_overridden_by_file": ("symlink_target_dir/",),
        "symlink_dir_overridden_by_dir": ("symlink_target_dir/",),
        "symlink_file_overridden_by_dir": ("symlink_target_file",),
        "symlink_file_overridden_by_file": ("symlink_target_file",),
        "dir_overridden_by_symlink_dir": {
            "file_in_dir_overridden_by_symlink_dir": "",
        },
        "dir_overridden_by_symlink_file": {
            "file_in_dir_overridden_by_symlink_file": "",
        },
        "file_overridden_by_symlink_dir": "",
        "file_overridden_by_symlink_file": "",
        "symlink_file_overridden_by_symlink_file": ("symlink_target_file",),
        "symlink_file_overridden_by_symlink_dir": ("symlink_target_file",),
        "symlink_dir_overridden_by_symlink_file": ("symlink_target_dir/",),
        "symlink_dir_overridden_by_symlink_dir": ("symlink_target_dir/",),
        "symlink_target_dir_overridden_by_file": ("starget_dir_overridden_by_file/",),
        "starget_dir_overridden_by_file": {
            "file_in_starget_dir_overridden_by_file": "",
        },
        "symlink_target_dir_overridden_by_dir": ("starget_dir_overridden_by_dir/",),
        "starget_dir_overridden_by_dir": {
            "file_in_starget_dir_overridden_by_dir": "",
        },
        "symlink_target_file_overridden_by_dir": ("starget_file_overridden_by_dir",),
        "starget_file_overridden_by_dir": "",
        "symlink_target_file_overridden_by_file": ("starget_file_overridden_by_file",),
        "starget_file_overridden_by_file": "",
    }
    tree_base["nested"] = copy.deepcopy(tree_base)
    tree_override = {
        "file_from_override": "override",
        "overridden_file": "quux",
        "common": {
            "file_from_override": "override",
            "overridden_file": "quux",
        },
        "empty": {
            "in_override": {},
            "common": {},
            "override_dir": "",
            "override_file": {},
            "nested_in_base_only": {},
            "symlinked": {
                "dir": {},
            },
        },
        "empty_symlinked_dir": ("empty/symlinked/",),
        "empty_symlinked_dir_2": ("empty_symlinked_dir/",),
        "deeply": {
            "nested": {
                "path": {
                    "overrides_file": "success",
                },
            },
        },
        "override": {
            "present": "",
        },
        "file_overridden_by_dir": {
            "file_in_overriding_dir": "success",
        },
        "dir_overridden_by_file": "success",
        "symlink_dir_overridden_by_dir": {
            "file_in_dir_overriding_symlink_dir": "success",
        },
        "symlink_dir_overridden_by_file": "success",
        "symlink_file_overridden_by_file": "success",
        "symlink_file_overridden_by_dir": {
            "file_in_dir_overriding_symlink_file": "success",
        },
        "other_symlink_target_dir": {
            "other_file_in_symlink_target": "success",
        },
        "other_symlink_target_file": "success",
        "dir_overridden_by_symlink_dir": ("other_symlink_target_dir/",),
        "dir_overridden_by_symlink_file": ("other_symlink_target_file",),
        "file_overridden_by_symlink_dir": ("other_symlink_target_dir/",),
        "file_overridden_by_symlink_file": ("other_symlink_target_file",),
        "symlink_file_overridden_by_symlink_file": ("other_symlink_target_file",),
        "symlink_file_overridden_by_symlink_dir": ("other_symlink_target_dir/",),
        "symlink_dir_overridden_by_symlink_file": ("other_symlink_target_file",),
        "symlink_dir_overridden_by_symlink_dir": ("other_symlink_target_dir/",),
        "starget_dir_overridden_by_file": "success",
        "starget_dir_overridden_by_dir": {
            "other_file_in_starget_dir_overridden_by_dir": "",
        },
        "starget_file_overridden_by_dir": {
            "file_in_starget_file_overridden_by_dir": "success",
        },
        "starget_file_overridden_by_file": "success",
        "symlink_to_parent": {
            "dir": ("../other_symlink_target_dir/",),
            "file": ("../file_from_override",),
        },
    }
    tree_override["nested"] = copy.deepcopy(tree_override)

    with create_file_tree(state_tree, {"base": tree_base}):
        with create_file_tree(state_tree_prod, {"override": tree_override}):
            yield


@pytest.mark.usefixtures("_recurse_merge_dirs")
@pytest.mark.parametrize("keep_symlinks", (False, True))
@pytest.mark.parametrize("include_empty", (False, True))
def test_recurse_merge(file, tmp_path, keep_symlinks, include_empty):
    tgt = tmp_path / "target"
    dirs = ("override", "base")
    sources = [
        f"salt://{src}" + ("?saltenv=prod" if src == "override" else "") for src in dirs
    ]
    ret = file.recurse(
        name=str(tgt),
        source=sources,
        merge=True,
        keep_symlinks=keep_symlinks,
        include_empty=include_empty,
    )
    assert ret.result is True
    assert tgt.is_dir()

    # Run the same assertions for both the root path and a nested dir
    for base in (tgt, tgt / "nested"):
        # Ensure unique dirs are all merged
        for tgt_dir in dirs:
            assert (base / tgt_dir / "present").exists()
        for shared_dir in (base, base / "common"):
            # Ensure unique files in shared dir are all merged
            for suffix in dirs:
                assert (shared_dir / f"file_from_{suffix}").is_file()
                assert (shared_dir / f"file_from_{suffix}").read_text() == suffix
            # Ensure shared files are overridden by first source
            assert (shared_dir / "overridden_file").is_file()
            assert (shared_dir / "overridden_file").read_text() == "quux"
        # Ensure dir <-> file overrides work
        for path in (
            ("file_overridden_by_dir", "file_in_overriding_dir"),
            ("dir_overridden_by_file",),
        ):
            assert base.joinpath(*path).is_file()
            assert base.joinpath(*path).read_text() == "success"
        assert (base / "deeply" / "nested" / "path" / "overrides_file").exists()

        # Sanity check include_empty
        for empty_dir in ("in_base", "in_override", "common"):
            assert ((base / "empty" / empty_dir).is_dir()) is include_empty
        # Ensure empty dirs can be overridden by files
        assert (base / "empty" / "override_dir").is_file()
        # Ensure empty dirs can override files when include_empty is set
        assert ((base / "empty" / "override_file").is_dir()) is include_empty
        # Ensure empty dirs in overrides don't block nested dirs/files
        assert (
            (base / "empty" / "nested_in_base_only" / "worked").is_dir()
        ) is include_empty
        assert (base / "empty" / "nested_in_base_only" / "nonempty" / "file").is_file()

        # Sanity check symlinks
        assert ((base / "symlinked_dir").is_symlink()) is keep_symlinks
        assert (base / "symlinked_dir").is_dir()
        assert (base / "symlink_target_dir").is_dir()
        for empty_symlink in ("empty_symlinked_dir", "empty_symlinked_dir_2"):
            assert ((base / empty_symlink).exists()) is include_empty
            assert ((base / empty_symlink).is_dir()) is include_empty
            assert ((base / empty_symlink).is_symlink()) is (
                include_empty and keep_symlinks
            )

        # Ensure symlinks can be overridden
        for symlink_overridden in (
            "symlink_dir_overridden_by_file",
            "symlink_dir_overridden_by_dir",
            "symlink_file_overridden_by_file",
            "symlink_file_overridden_by_dir",
        ):
            assert not (base / symlink_overridden).is_symlink()
            if symlink_overridden.endswith("file"):
                assert (base / symlink_overridden).read_text() == "success"
            else:
                assert (
                    base
                    / symlink_overridden
                    / (
                        "file_in_dir_overriding_"
                        + symlink_overridden.split("_overridden", maxsplit=1)[0]
                    )
                ).read_text() == "success"

        # Ensure symlinks can override files/directories and other symlinks
        for symlink in (
            "dir_overridden_by_symlink_dir",
            "dir_overridden_by_symlink_file",
            "file_overridden_by_symlink_dir",
            "file_overridden_by_symlink_file",
            "symlink_dir_overridden_by_symlink_dir",
            "symlink_dir_overridden_by_symlink_file",
            "symlink_file_overridden_by_symlink_dir",
            "symlink_file_overridden_by_symlink_file",
        ):
            assert ((base / symlink).is_symlink()) is keep_symlinks
            if symlink.endswith("file"):
                assert (base / symlink).read_text() == "success"
            else:
                assert (
                    base / symlink / "other_file_in_symlink_target"
                ).read_text() == "success"

        # Ensure symlinked dirs are merged when not preserving symlinks
        assert (
            base / "symlink_dir_overridden_by_dir" / "file_in_symlink_target"
        ).exists() is not keep_symlinks
        assert (
            base / "symlink_dir_overridden_by_symlink_dir" / "file_in_symlink_target"
        ).exists() is not keep_symlinks
        assert (
            base
            / "dir_overridden_by_symlink_dir"
            / "file_in_dir_overridden_by_symlink_dir"
        ).exists() is not keep_symlinks

        # Ensure overridden symlink targets don't cause surprises
        assert (base / "symlink_target_file_overridden_by_file").exists()
        assert (
            (base / "symlink_target_file_overridden_by_file").is_symlink()
        ) is keep_symlinks
        assert (
            (base / "symlink_target_file_overridden_by_file").read_text() == "success"
        ) is keep_symlinks
        assert (
            (base / "symlink_target_dir_overridden_by_dir").is_symlink()
        ) is keep_symlinks
        assert (base / "symlink_target_dir_overridden_by_dir").is_dir()

        assert not (base / "symlink_target_dir_overridden_by_file").is_symlink()
        assert (
            (base / "symlink_target_dir_overridden_by_file").exists()
        ) is not keep_symlinks
        assert (
            (base / "symlink_target_dir_overridden_by_file").is_dir()
        ) is not keep_symlinks

        assert not (base / "symlink_target_file_overridden_by_dir").is_symlink()
        assert (
            (base / "symlink_target_file_overridden_by_dir").exists()
        ) is not keep_symlinks
        assert (
            (base / "symlink_target_file_overridden_by_dir").is_file()
        ) is not keep_symlinks

        # Ensure symlinks to parent paths works
        assert (base / "symlink_to_parent/dir").exists()
        assert (base / "symlink_to_parent/dir").is_symlink() is keep_symlinks
        assert (base / "symlink_to_parent/dir").is_dir()
        assert (base / "symlink_to_parent/dir/other_file_in_symlink_target").exists()
        assert (base / "symlink_to_parent/file").exists()
        assert (base / "symlink_to_parent/file").is_symlink() is keep_symlinks
        assert (base / "symlink_to_parent/file").is_file()


@pytest.mark.parametrize("include_empty", (False, True))
def test_recurse_merge_keep_symlinks_broken_symlinks_are_kept(
    file, state_tree, tmp_path, include_empty
):
    """
    When ``keep_symlinks`` is set, broken symlinks should be kept.
    They cause an exception when keep_symlinks is false
    (and the fileserver follows them, ``fileserver_followsymlinks``).

    This is not specific to ``merge=True``, but should be tested regardless.
    """
    tree = {
        "base": {"foo": {"random_file": "", "broken_link": ("../nonexistent",)}},
        "override": {"other_broken_link": ("42",)},
    }
    with create_file_tree(state_tree, tree):
        tgt = tmp_path / "target"
        dirs = ("override", "base")
        sources = [f"salt://{src}" for src in dirs]
        ret = file.recurse(
            name=str(tgt),
            source=sources,
            merge=True,
            keep_symlinks=True,
            include_empty=include_empty,
        )
        assert ret.result is True
        assert (tgt / "foo" / "broken_link").is_symlink()
        assert (tgt / "foo" / "random_file").is_file()
        assert (tgt / "other_broken_link").is_symlink()


@pytest.mark.skip_on_windows(reason="'dir_mode' is not supported on Windows")
def test_recurse_issue_34945(file, tmp_path, state_tree):
    """
    This tests the case where the source dir for the file.recurse state
    does not contain any files (only subdirectories), and the dir_mode is
    being managed. For a long time, this corner case resulted in the top
    level of the destination directory being created with the wrong initial
    permissions, a problem that would be corrected later on in the
    file.recurse state via running state.directory. However, the
    file.directory state only gets called when there are files to be
    managed in that directory, and when the source directory contains only
    subdirectories, the incorrectly-set initial perms would not be
    repaired.

    This was fixed in https://github.com/saltstack/salt/pull/35309

    """
    dir_mode = "2775"
    issue_dir = "issue-34945"
    src_dir = state_tree / issue_dir
    src_file = src_dir / "foo" / "bar" / "baz" / "test_file"
    src_file.parent.mkdir(mode=0o0755, parents=True)
    src_file.write_text("Hello World!\n")

    name = tmp_path / issue_dir

    ret = file.recurse(name=str(name), source=f"salt://{issue_dir}", dir_mode=dir_mode)
    assert ret.result is True
    assert name.is_dir()
    assert src_dir.stat().st_mode != name.stat().st_mode
    actual_dir_mode = oct(stat.S_IMODE(name.stat().st_mode))[-4:]
    assert actual_dir_mode == dir_mode


def test_recurse_issue_40578(file, state_tree, tmp_path):
    """
    This ensures that the state doesn't raise an exception when it
    encounters a file with a unicode filename in the process of invoking
    file.source_list.
    """
    name = tmp_path / "dst-dir"
    src_dir = state_tree / "соль"
    src_dir.mkdir()
    filenames = ("foo.txt", "спам.txt", "яйца.txt")
    for fname in filenames:
        src_dir.joinpath(fname).write_text("bar")

    ret = file.recurse(name=str(name), source="salt://соль")
    assert ret.result is True
    assert sorted(p.name for p in name.iterdir()) == sorted(filenames)


@pytest.mark.skip_on_windows(reason="Mode not available in Windows")
def test_issue_2726_mode_kwarg(modules, tmp_path, state_tree):
    dir1 = tmp_path / "dir1"
    dir2 = tmp_path / "dir2"
    with pytest.helpers.temp_file(
        "testfile", directory=state_tree, contents="test file contents"
    ), pytest.helpers.temp_file(
        "testfile",
        directory=state_tree / "testappend",
        contents="test file append contents",
    ):
        # Let's test for the wrong usage approach
        bad_mode_kwarg_testfile = dir1 / "bad_mode_kwarg" / "testfile"
        bad_template = [
            f"{bad_mode_kwarg_testfile}:",
            "  file.recurse:",
            "    - source: salt://testfile",
            "    - mode: 644",
        ]
        ret = modules.state.template_str("\n".join(bad_template))
        for state_run in ret:
            assert state_run.result is False
            assert (
                "'mode' is not allowed in 'file.recurse'. Please use 'file_mode' and 'dir_mode'."
                in state_run.comment
            )
            assert (
                "TypeError: managed() got multiple values for keyword "
                "argument 'mode'" not in state_run.comment
            )

        # Now, the correct usage approach
        good_mode_kwargs_testfile = dir2 / "good_mode_kwargs" / "testappend"
        good_template = [
            f"{good_mode_kwargs_testfile}:",
            "  file.recurse:",
            "    - source: salt://testappend",
            "    - dir_mode: 744",
            "    - file_mode: 644",
        ]
        ret = modules.state.template_str("\n".join(good_template))
        for state_run in ret:
            assert state_run.result is True


def test_issue_64630_keep_symlinks_true(file, symlink_scenario_1, tmp_path):
    """
    Make sure that symlinks are created and that there isn't an error when there
    are no conflicting target files
    """
    target_dir = tmp_path / symlink_scenario_1  # Target for the file.recurse state
    target_file = target_dir / "source_file.txt"
    target_symlink = target_dir / "symlink"

    ret = file.recurse(
        name=str(target_dir), source=f"salt://{target_dir.name}", keep_symlinks=True
    )
    assert ret.result is True

    assert target_dir.exists()
    assert target_file.is_file()
    assert target_symlink.is_symlink()


def test_issue_64630_keep_symlinks_false(file, symlink_scenario_1, tmp_path):
    """
    Make sure that symlinks are created as files and that there isn't an error
    """
    target_dir = tmp_path / symlink_scenario_1  # Target for the file.recurse state
    target_file = target_dir / "source_file.txt"
    target_symlink = target_dir / "symlink"

    ret = file.recurse(
        name=str(target_dir), source=f"salt://{target_dir.name}", keep_symlinks=False
    )
    assert ret.result is True

    assert target_dir.exists()
    assert target_file.is_file()
    assert target_symlink.is_file()
    assert target_file.read_text() == target_symlink.read_text()


def test_issue_64630_keep_symlinks_conflicting_force_symlinks_false(
    file, symlink_scenario_1, tmp_path
):
    """
    Make sure that symlinks are not created when there is a conflict. The state
    should return False
    """
    target_dir = tmp_path / symlink_scenario_1  # Target for the file.recurse state
    target_file = target_dir / "source_file.txt"
    target_symlink = target_dir / "symlink"

    # Create the conflicting file
    target_symlink.parent.mkdir(parents=True)
    target_symlink.touch()
    assert target_symlink.is_file()

    ret = file.recurse(
        name=str(target_dir),
        source=f"salt://{target_dir.name}",
        keep_symlinks=True,
        force_symlinks=False,
    )
    # We expect it to fail
    assert ret.result is False

    # And files not to be created properly
    assert target_dir.exists()
    assert target_file.is_file()
    assert target_symlink.is_file()


def test_issue_64630_keep_symlinks_conflicting_force_symlinks_true(
    file, symlink_scenario_1, tmp_path
):
    """
    Make sure that symlinks are created when there is a conflict with an
    existing file.
    """
    target_dir = tmp_path / symlink_scenario_1  # Target for the file.recurse state
    target_file = target_dir / "source_file.txt"
    target_symlink = target_dir / "symlink"

    # Create the conflicting file
    target_symlink.parent.mkdir(parents=True)
    target_symlink.touch()
    assert target_symlink.is_file()

    ret = file.recurse(
        name=str(target_dir),
        source=f"salt://{target_dir.name}",
        force_symlinks=True,
        keep_symlinks=True,
    )
    assert ret.result is True

    assert target_dir.exists()
    assert target_file.is_file()
    assert target_symlink.is_symlink()


def test_issue_64630_keep_symlinks_similar_names(file, symlink_scenario_3, tmp_path):
    """
    Make sure that symlinks are created when there is a file that shares part
    of the name of the actual symlink file. I'm not sure what I'm testing here
    as I couldn't really get this to fail either way
    """
    target_dir = tmp_path / symlink_scenario_3  # Target for the file.recurse state
    # symlink target, but has the same name as the symlink itself
    target_source = target_dir / "not_a_symlink" / "symlink"
    target_symlink = target_dir / "symlink"
    decoy_file = target_dir / "notasymlink"
    just_a_file = target_dir / "just_a_file.txt"

    ret = file.recurse(
        name=str(target_dir), source=f"salt://{target_dir.name}", keep_symlinks=True
    )
    assert ret.result is True

    assert target_dir.exists()
    assert target_source.is_file()
    assert decoy_file.is_file()
    assert just_a_file.is_file()
    assert target_symlink.is_symlink()


def test_issue_62117(file, symlink_scenario_2, tmp_path):
    target_dir = tmp_path / symlink_scenario_2 / "test"
    target_file_1 = target_dir / "test1"
    target_file_2 = target_dir / "test2"
    target_file_3 = target_dir / "test3"
    target_symlink = target_dir / "test"

    ret = file.recurse(
        name=str(target_dir),
        source=f"salt://{target_dir.parent.name}/test",
        clean=True,
        keep_symlinks=True,
    )
    assert ret.result is True

    assert target_dir.exists()
    assert target_file_1.is_file()
    assert target_file_2.is_file()
    assert target_file_3.is_file()
    assert target_symlink.is_symlink()
