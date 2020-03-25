# Import python libs
import copy
import os

import salt.crypt
import salt.pillar
import salt.transport.client
import salt.utils.crypt
import salt.utils.stringutils
from salt.exceptions import SaltClientError, SaltReqTimeoutError

# Import third party libs
try:
    from M2Crypto import RSA

    HAS_M2 = True
except ImportError:
    HAS_M2 = False

if not HAS_M2:
    try:
        from Cryptodome.Cipher import PKCS1_OAEP

        HAS_CDOME = True
    except ImportError:
        HAS_CDOME = False

if not HAS_M2 and not HAS_CDOME:
    try:
        from Crypto.Cipher import PKCS1_OAEP
    except ImportError:
        # No need for crypt in local mode
        pass


def _minion_sign_in_payload(id_):
    """
    Generates the payload used to authenticate with the master
    server. This payload consists of the passed in id_ and the ssh
    public key to encrypt the AES key sent back from the master.
    :return: Payload dictionary
    :rtype: dict
    """
    payload = {"cmd": "_auth", "id": id_}
    mpub = "minion_master.pub"
    token = salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string())
    pub_path = os.path.join(__opts__["pki_dir"], "minion.pub")
    try:
        pubkey_path = os.path.join(__opts__["pki_dir"], mpub)
        pub = salt.crypt.get_rsa_pub_key(pubkey_path)
        if HAS_M2:
            payload["token"] = pub.public_encrypt(token, RSA.pkcs1_oaep_padding)
        else:
            cipher = PKCS1_OAEP.new(pub)
            payload["token"] = cipher.encrypt(token)
    except Exception:
        pass
    with salt.utils.files.fopen(pub_path) as f:
        payload["pub"] = f.read()
    return payload


def keys():
    """
    Send the salt master a collection of fake keys, these are use to populate the master's key
    cache to facilitate emulating many minions inside of this single minion
    """
    channel = salt.transport.client.ReqChannel.factory(__opts__, crypt="clear")

    try:
        for ind in range(__opts__.get("legion_fakes", 10)):
            id_ = "{}_{}".format(__opts__["id"], ind)
            sign_in_payload = _minion_sign_in_payload(id_)
            channel.send(
                sign_in_payload, tries=0, timeout=30,
            )
    except SaltReqTimeoutError as e:
        raise SaltClientError(
            f"Attempt to authenticate with the salt master failed with timeout error: {e}",
        )
    finally:
        channel.close()


def cache():
    """
    Populate the master with the fake minions' grains and pillars by requesting pillars on behalf
    of the fakes
    """
    for ind in range(__opts__.get("legion_fakes", 10)):
        id_ = "{}_{}".format(__opts__["id"], ind)
        opts = copy.deepcopy(__opts__)
        opts["id"] = id_
        pillar = salt.pillar.get_pillar(
            __opts__, __grains__, id_, pillar_override=None, pillarenv=None
        )
        pillar.compile_pillar()
