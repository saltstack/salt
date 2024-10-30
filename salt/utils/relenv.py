import os

__virtualname__ = "relenv"

try:
    import relenv.fetch  # noqa

    HAS_RELENV = True
except ImportError:
    HAS_RELENV = False


def __virtual__():
    if HAS_RELENV:
        return __virtualname__
    return (False, "Pip install `relenv` to use this feature")


def gen_relenv(
    kernel,
    os_arch,
):
    """
    Deploy salt-relenv.
    :param kernel: The detected OS (e.g., 'linux', 'darwin', 'windows').
    :param os_arch: The detected architecture (e.g., 'amd64', 'x86_64', 'arm64').
    :return: The path to the recompressed .tgz file.
    """
    triplet = relenv.fetch.get_triplet(machine=os_arch, plat=kernel)
    version = os.environ.get("RELENV_FETCH_VERSION", relenv.fetch.__version__)
    python = relenv.fetch.platform_versions()[0]

    relenv.fetch.fetch(version, triplet, python)

    return os.path.join(
        relenv.fetch.work_dir("build", relenv.fetch.DATA_DIR),
        f"{python}-{triplet}.tar.xz",
    )
