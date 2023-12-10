"""
Load up the libvirt keys into Pillar for a given minion if said keys have been
generated using the libvirt key runner

:depends: certtool
"""
import os
import subprocess

import salt.utils.files
import salt.utils.path
import salt.utils.stringutils

# Don't "fix" the above docstring to put it on two lines, as the sphinx
# autosummary pulls only the first line for its description.


def __virtual__():
    return salt.utils.path.which("certtool") is not None


def ext_pillar(minion_id, pillar, command):
    """
    Read in the generated libvirt keys
    """
    key_dir = os.path.join(__opts__["pki_dir"], "libvirt", minion_id)
    cacert = os.path.join(__opts__["pki_dir"], "libvirt", "cacert.pem")
    if not os.path.isdir(key_dir):
        # No keys have been generated
        gen_hyper_keys(
            minion_id,
            pillar.get("ext_pillar_virt.country", "US"),
            pillar.get("ext_pillar_virt.st", "Utah"),
            pillar.get("ext_pillar_virt.locality", "Salt Lake City"),
            pillar.get("ext_pillar_virt.organization", "Salted"),
            pillar.get("ext_pillar_virt.expiration_days", "365"),
        )
    ret = {}
    for key in os.listdir(key_dir):
        if not key.endswith(".pem"):
            continue
        fn_ = os.path.join(key_dir, key)
        with salt.utils.files.fopen(fn_, "r") as fp_:
            ret["libvirt.{}".format(key)] = salt.utils.stringutils.to_unicode(
                fp_.read()
            )
    with salt.utils.files.fopen(cacert, "r") as fp_:
        ret["libvirt.cacert.pem"] = salt.utils.stringutils.to_unicode(fp_.read())
    return ret


def gen_hyper_keys(
    minion_id,
    country="US",
    state="Utah",
    locality="Salt Lake City",
    organization="Salted",
    expiration_days="365",
):
    """
    Generate the keys to be used by libvirt hypervisors, this routine gens
    the keys and applies them to the pillar for the hypervisor minions
    """
    key_dir = os.path.join(__opts__["pki_dir"], "libvirt")
    if not os.path.isdir(key_dir):
        os.makedirs(key_dir)
    cakey = os.path.join(key_dir, "cakey.pem")
    cacert = os.path.join(key_dir, "cacert.pem")
    cainfo = os.path.join(key_dir, "ca.info")
    if not os.path.isfile(cainfo):
        with salt.utils.files.fopen(cainfo, "w+") as fp_:
            fp_.write("cn = salted\nca\ncert_signing_key")
    if not os.path.isfile(cakey):
        proc = subprocess.run(
            ["certtool", "--generate-privkey"],
            stdout=subprocess.PIPE,
            universal_newlines=True,
            check=True,
        )
        with salt.utils.files.fopen(cakey, "w") as wfh:
            wfh.write(proc.stdout)
    if not os.path.isfile(cacert):
        subprocess.call(
            [
                "certtool",
                "--generate-self-signed",
                "--load-privkey",
                cakey,
                "--template",
                cainfo,
                "--outfile",
                cacert,
            ]
        )
    sub_dir = os.path.join(key_dir, minion_id)
    if not os.path.isdir(sub_dir):
        os.makedirs(sub_dir)
    priv = os.path.join(sub_dir, "serverkey.pem")
    cert = os.path.join(sub_dir, "servercert.pem")
    srvinfo = os.path.join(sub_dir, "server.info")
    cpriv = os.path.join(sub_dir, "clientkey.pem")
    ccert = os.path.join(sub_dir, "clientcert.pem")
    clientinfo = os.path.join(sub_dir, "client.info")
    if not os.path.isfile(srvinfo):
        with salt.utils.files.fopen(srvinfo, "w+") as fp_:
            infodat = salt.utils.stringutils.to_str(
                "organization = salted\ncn = {}\ntls_www_server"
                "\nencryption_key\nsigning_key"
                "\ndigitalSignature\nexpiration_days = {}".format(
                    __grains__["fqdn"], expiration_days
                )
            )
            fp_.write(infodat)
    if not os.path.isfile(priv):
        proc = subprocess.run(
            ["certtool", "--generate-privkey"],
            stdout=subprocess.PIPE,
            universal_newlines=True,
            check=True,
        )
        with salt.utils.files.fopen(priv, "w") as wfh:
            wfh.write(proc.stdout)
    if not os.path.isfile(cert):
        subprocess.call(
            [
                "certtool",
                "--generate-certificate",
                "--load-privkey",
                priv,
                "--load-ca-certificate",
                cacert,
                "--load-ca-privkey",
                cakey,
                "--template",
                srvinfo,
                "--outfile",
                cert,
            ]
        )
    if not os.path.isfile(clientinfo):
        with salt.utils.files.fopen(clientinfo, "w+") as fp_:
            infodat = salt.utils.stringutils.to_str(
                "country = {}\nstate = {}\nlocality = {}\n"
                "organization = {}\ncn = {}\n"
                "tls_www_client\nencryption_key\nsigning_key\n"
                "digitalSignature".format(
                    country, state, locality, organization, __grains__["fqdn"]
                )
            )
            fp_.write(infodat)
    if not os.path.isfile(cpriv):
        proc = subprocess.run(
            ["certtool", "--generate-privkey"],
            stdout=subprocess.PIPE,
            universal_newlines=True,
            check=True,
        )
        with salt.utils.files.fopen(cpriv, "w") as wfh:
            wfh.write(proc.stdout)
    if not os.path.isfile(ccert):
        subprocess.call(
            [
                "certtool",
                "--generate-certificate",
                "--load-privkey",
                cpriv,
                "--load-ca-certificate",
                cacert,
                "--load-ca-privkey",
                cakey,
                "--template",
                clientinfo,
                "--outfile",
                ccert,
            ]
        )
