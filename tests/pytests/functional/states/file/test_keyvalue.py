import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


def test_keyvalue(file, tmp_path):
    """
    file.keyvalue
    """
    contents = """
        # This is the sshd server system-wide configuration file.  See
        # sshd_config(5) for more information.

        # The strategy used for options in the default sshd_config shipped with
        # OpenSSH is to specify options with their default value where
        # possible, but leave them commented.  Uncommented options override the
        # default value.

        #Port 22
        #AddressFamily any
        #ListenAddress 0.0.0.0
        #ListenAddress ::

        #HostKey /etc/ssh/ssh_host_rsa_key
        #HostKey /etc/ssh/ssh_host_ecdsa_key
        #HostKey /etc/ssh/ssh_host_ed25519_key

        # Ciphers and keying
        #RekeyLimit default none

        # Logging
        #SyslogFacility AUTH
        #LogLevel INFO

        # Authentication:

        #LoginGraceTime 2m
        #PermitRootLogin prohibit-password
        #StrictModes yes
        #MaxAuthTries 6
        #MaxSessions 10
        """
    with pytest.helpers.temp_file(
        "sshd_config", contents=contents, directory=tmp_path
    ) as name:
        ret = file.keyvalue(
            name=str(name),
            key="permitrootlogin",
            value="no",
            separator=" ",
            uncomment=" #",
            key_ignore_case=True,
        )
        assert ret.result is True
        changed_contents = name.read_text()
        assert "#PermitRootLogin" not in changed_contents
        assert "prohibit-password" not in changed_contents
        assert "PermitRootLogin no" in changed_contents
