import hashlib
import os

import dnf
from dnfpluginscore import _, logger


class DnfNotifyPlugin(dnf.Plugin):
    def __init__(self, base, cli):
        super().__init__(base, cli)
        self.base = base
        self.cookie_file = "/var/cache/salt/minion/rpmdb.cookie"
        if os.path.exists("/var/lib/rpm/rpmdb.sqlite"):
            self.rpmdb_file = "/var/lib/rpm/rpmdb.sqlite"
        else:
            self.rpmdb_file = "/var/lib/rpm/Packages"

    def transaction(self):
        if "SALT_RUNNING" not in os.environ:
            try:
                ck_dir = os.path.dirname(self.cookie_file)
                if not os.path.exists(ck_dir):
                    os.makedirs(ck_dir)
                with open(self.cookie_file, "w") as ck_fh:
                    ck_fh.write(
                        "{chksum} {mtime}\n".format(
                            chksum=self._get_checksum(), mtime=self._get_mtime()
                        )
                    )
            except OSError as e:
                logger.error(_("Unable to save cookie file: %s"), e)

    def _get_mtime(self):
        """
        Get the modified time of the RPM Database.

        Returns:
            Unix ticks
        """
        return (
            os.path.exists(self.rpmdb_file)
            and int(os.path.getmtime(self.rpmdb_file))
            or 0
        )

    def _get_checksum(self):
        """
        Get the checksum of the RPM Database.

        Returns:
            hexdigest
        """
        digest = hashlib.sha256()
        with open(self.rpmdb_file, "rb") as rpm_db_fh:
            while True:
                buff = rpm_db_fh.read(0x1000)
                if not buff:
                    break
                digest.update(buff)
        return digest.hexdigest()
