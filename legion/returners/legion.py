# Import python libs
import logging

# Import Salt Libs
import salt.crypt
import salt.transport.client
import salt.serializers.msgpack

log = logging.getLogger(__name__)


def returner(ret):
    log.error(ret)
    if ret["fun"].startswith("legion"):
        return
    channel = salt.transport.client.ReqChannel.factory(__opts__)
    for ind in range(__opts__.get("legion_fakes", 10)):
        id_ = "{}_{}".format(__opts__["id"], ind)
        load = {
            "cmd": "_return",
            "id": id_,
            "jid": ret[u"jid"],
            "fun": ret[u"fun"],
            "fun_args": ret.get(u"fun_args", []),
            "return": ret[u"return"],
            "retcode": ret[u"retcode"],
            "success": ret[u"success"],
        }
        if __opts__["minion_sign_messages"]:
            log.trace("Signing event to be published onto the bus.")
            minion_privkey_path = os.path.join(__opts__["pki_dir"], "minion.pem")
            sig = salt.crypt.sign_message(
                minion_privkey_path, salt.serializers.msgpack.serialize(load)
            )
            load["sig"] = sig
        master_ret = channel.send(load, timeout=30)
    channel.close()
