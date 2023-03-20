def linux_distribution():
    """ """
    # Late import so that when getting called from setup.py does not break
    import distro

    return distro.id(), distro.version(best=True), distro.codename()
