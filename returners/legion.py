# Import python libs
import logging

# Import Salt Libs
import salt.crypt
import salt.transport.client
import salt.serializers.msgpack

log = logging.getLogger(__name__)


def returner(ret):
    if ret['fun'].startswith('legion'):
        return
    channel = salt.transport.client.ReqChannel.factory(__opts__)
    for ind in range(__opts__.get('legion_fakes', 10)):
        id_ = '{}_{}'.format(__opts__['id'], ind)
        load = {
                'cmd': '_return',
                'id': id_,
                'jid': ret['jid'],
                'fun': ret['fun'],
                'fun_args': ret.get('arg', []),
                'return': True,
                'retcode': 0,
                'success': True,
                }
        if __opts__['minion_sign_messages']:
            log.trace('Signing event to be published onto the bus.')
            minion_privkey_path = os.path.join(__opts__['pki_dir'], 'minion.pem')
            sig = salt.crypt.sign_message(minion_privkey_path, salt.serializers.msgpack.serialize(load))
            load['sig'] = sig
        master_ret = channel.send(load, timeout=30)
    channel.close()
