#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
The minionswarm script will start a group of salt minions with different ids
on a single system to test scale capabilities
'''
# pylint: disable=resource-leakage
# Import Python Libs
from __future__ import absolute_import, print_function
import os
import time
import signal
import optparse
import subprocess
import random
import tempfile
import shutil
import sys
import hashlib
import uuid
import multiprocessing

from shutil import copyfile

# Import salt libs
import salt
import salt.config
import salt.modules
import salt.returners
import salt.utils.files
import salt.utils.platform
import salt.utils.yaml
import salt.utils.event

# Import third party libs
from salt.ext import six
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin

if salt.utils.platform.is_windows():
    import salt.utils.win_functions
else:
    import pwd

OSES = [
        'Arch',
        'Ubuntu',
        'Debian',
        'CentOS',
        'Fedora',
        'Gentoo',
        'AIX',
        'Solaris',
        ]
VERS = [
        '2014.1.6',
        '2014.7.4',
        '2015.5.5',
        '2015.8.0',
        ]


def event_listener(accepted_minions, cached_ret):
    opts = salt.config.client_config('/etc/salt/master')
    event = salt.utils.event.get_event(
            'master',
            sock_dir=opts['sock_dir'],
            transport=opts['transport'],
            opts=opts)

    while 1:
        data = event.get_event()
        if data:
            if 'act' in data:
                mid = data['id']
                if mid not in accepted_minions:
                    accepted_minions[mid] = True

            elif 'return' in data and 'fun' in data and data['fun'] == 'legion.cache':
                mid = data['id']
                if mid not in cached_ret:
                    cached_ret[mid] = True

        time.sleep(0.1)


def this_user():
    '''
    Get the user associated with the current process.
    '''
    if salt.utils.platform.is_windows():
        return salt.utils.win_functions.get_current_user(with_domain=False)
    return pwd.getpwuid(os.getuid())[0]


def parse():
    '''
    Parse the cli options
    '''
    parser = optparse.OptionParser()
    parser.add_option(
        '-l',
        '--legion',
        dest='legion',
        default=0,
        type='int',
        help='The number of extra legion fakes')
    parser.add_option(
        '-m',
        '--minions',
        dest='minions',
        default=5,
        type='int',
        help='The number of minions to make')
    parser.add_option(
        '-M',
        action='store_true',
        dest='master_too',
        default=False,
        help='Run a local master and tell the minions to connect to it')
    parser.add_option(
        '--master',
        dest='master',
        default='salt',
        help='The location of the salt master that this swarm will serve')
    parser.add_option(
        '--name',
        '-n',
        dest='name',
        default='ms',
        help=('Give the minions an alternative id prefix, this is used '
              'when minions from many systems are being aggregated onto '
              'a single master'))
    parser.add_option(
        '--rand-os',
        dest='rand_os',
        default=False,
        action='store_true',
        help='Each Minion claims a different os grain')
    parser.add_option(
        '--rand-ver',
        dest='rand_ver',
        default=False,
        action='store_true',
        help='Each Minion claims a different version grain')
    parser.add_option(
        '--rand-machine-id',
        dest='rand_machine_id',
        default=False,
        action='store_true',
        help='Each Minion claims a different machine id grain')
    parser.add_option(
        '--rand-uuid',
        dest='rand_uuid',
        default=False,
        action='store_true',
        help='Each Minion claims a different UUID grain')
    parser.add_option(
        '-k',
        '--keep-modules',
        dest='keep',
        default='',
        help='A comma delimited list of modules to enable')
    parser.add_option(
        '-f',
        '--foreground',
        dest='foreground',
        default=False,
        action='store_true',
        help=('Run the minions with debug output of the swarm going to '
              'the terminal'))
    parser.add_option(
        '--temp-dir',
        dest='temp_dir',
        default=None,
        help='Place temporary files/directories here')
    parser.add_option(
        '--no-clean',
        action='store_true',
        default=False,
        help='Don\'t cleanup temporary files/directories')
    parser.add_option(
        '--root-dir',
        dest='root_dir',
        default=None,
        help='Override the minion root_dir config')
    parser.add_option(
        '--transport',
        dest='transport',
        default='zeromq',
        help='Declare which transport to use, default is zeromq')
    parser.add_option(
        '--start-delay',
        dest='start_delay',
        default=0.0,
        type='float',
        help='Seconds to wait between minion starts')
    parser.add_option(
        '--legion-start-delay',
        dest='legion_start_delay',
        default=0.0,
        type='float',
        help='Seconds to wait to issue legion commands')
    parser.add_option(
        '-c', '--config-dir', default='',
        help=('Pass in a configuration directory containing base configuration.')
        )
    parser.add_option('-u', '--user', default=this_user())
    parser.add_option('--run-modules',
                      help=('Call legion.keys and legion.cache modules as minions start. '
                            'This requires legion to be ran on the salt master that they '
                            'are connecting to.'),
                      dest='run_modules',
                      action='store_true',
                      default=False)

    options, _args = parser.parse_args()

    opts = {}

    for key, val in six.iteritems(options.__dict__):
        opts[key] = val

    return opts


class Swarm(object):
    '''
    Create a swarm of minions
    '''
    def __init__(self, opts, accepted_minions, cached_ret):
        self.opts = opts
        self.accepted_minions = accepted_minions
        self.cached_ret = cached_ret

        # If given a temp_dir, use it for temporary files
        if opts['temp_dir']:
            self.swarm_root = os.path.abspath(opts['temp_dir'])
        else:
            # If given a root_dir, keep the tmp files there as well
            if opts['root_dir']:
                tmpdir = os.path.join(opts['root_dir'], 'tmp')
            else:
                tmpdir = opts['root_dir']
            self.swarm_root = tempfile.mkdtemp(
                prefix='mswarm-root', suffix='.d',
                dir=tmpdir)

        if self.opts['transport'] == 'zeromq':
            self.pki = self._pki_dir()
        self.zfill = len(str(self.opts['minions']))

        self.confs = []
        self.minions = []

        random.seed(0)

    def _pki_dir(self):
        '''
        Create the shared pki directory
        '''
        path = os.path.join(self.swarm_root, 'pki')
        if not os.path.exists(path):
            os.makedirs(path)

            print('Creating shared pki keys for the swarm on: {0}'.format(path))

            with open(os.devnull, 'w') as stdout:
                subprocess.call(
                  'salt-key -c {0} --gen-keys minion --gen-keys-dir {0} '
                  '--log-file {1} --user {2}'.format(
                      path, os.path.join(path, 'keys.log'), self.opts['user'],
                  ), shell=True, stdout=stdout
                )
            print('Keys generated')
        return path

    def start(self):
        '''
        Start the magic!!
        '''
        if self.opts['master_too']:
            print('Starting master...')
            master_swarm = MasterSwarm(self.opts)
            master_swarm.start()

        print('Starting minions...')
        minions = MinionSwarm(self.opts, self.accepted_minions, self.cached_ret)
        minions.start_minions()

        print('All {0} minions have started.'.format(self.opts['minions']))
        print('Waiting for CTRL-C to properly shutdown minions...')
        while True:
            try:
                time.sleep(5)
            except KeyboardInterrupt:
                print('\nShutting down minions')
                self.clean_configs()
                break

    def shutdown(self):
        '''
        Tear it all down
        '''
        print('Killing any remaining running minions')
        with open(os.devnull, 'w') as stdout:
            subprocess.call(
                'pkill -KILL -f "python.*salt-minion"',
                shell=True,
                stdout=stdout,
            )
            if self.opts['master_too']:
                print('Killing any remaining masters')
                subprocess.call(
                    'pkill -KILL -f "python.*salt-master"',
                    shell=True,
                    stdout=stdout,
                )
        if not self.opts['no_clean']:
            print('Remove ALL related temp files/directories')
            shutil.rmtree(self.swarm_root)
        print('Done')

    def clean_configs(self):
        '''
        Clean up the config files
        '''
        for conf in self.confs:
            path = conf['path']
            pidfile = '{0}.pid'.format(path)
            try:
                try:
                    with salt.utils.files.fopen(pidfile) as fp_:
                        pid = int(fp_.read().strip())
                    os.kill(pid, signal.SIGTERM)
                except ValueError:
                    pass
                if os.path.exists(pidfile):
                    os.remove(pidfile)
                if not self.opts['no_clean']:
                    shutil.rmtree(path)
            except (OSError, IOError):
                pass


class MinionSwarm(Swarm):
    '''
    Create minions
    '''
    def start_minions(self):
        '''
        Iterate over the config files and start up the minions
        '''
        # if self.opts['legion']:
        #     mydir = os.path.dirname(__file__)
        #     returner = os.path.join(mydir, 'returners', 'legion.py')
        #     returner_dst = os.path.join(os.path.dirname(salt.returners.__file__), 'legion.py')

        #     module = os.path.join(mydir, 'modules', 'legion.py')
        #     module_dst = os.path.join(os.path.dirname(salt.modules.__file__), 'legion.py')

        #     copyfile(returner, returner_dst)
        #     copyfile(module, module_dst)

        self.prep_configs()
        for conf in self.confs:
            path = conf['path']
            cmd = 'salt-minion -c {0} --pid-file {1}'.format(
                    path,
                    '{0}.pid'.format(path)
                    )
            if self.opts['foreground']:
                cmd += ' -l info &'
            else:
                cmd += ' -d &'
            with open(os.devnull, 'w') as stdout:
                if self.opts['foreground']:
                    stdout = sys.stdout
                subprocess.call(cmd, shell=True, stdout=stdout)

            minion = conf['id']
            self.wait_for([minion])
            time.sleep(self.opts['start_delay'])

            if self.opts['legion'] and self.opts['run_modules']:
                with open(os.devnull, 'w') as stdout:
                    subprocess.call("salt '{}' legion.keys".format(minion), shell=True, stdout=stdout)
                    minions = ['{}_{}'.format(minion, m) for m in range(self.opts['legion'])]
                    self.wait_for(minions)
                    subprocess.call("salt '{}' legion.cache".format(minion), shell=True, stdout=stdout)
                    self.wait_for([minion], attr='cached_ret')
                    time.sleep(self.opts['legion_start_delay'])

    def wait_for(self, minions, attr='accepted_minions'):
        count = 0
        print('Waiting for {}:'.format(attr), minions, end=' ... ')
        while 1:
            for m in minions:
                if m in getattr(self, attr):
                    count += 1

            if count >= len(minions):
                print('✓')
                return

            time.sleep(2)

    def mkconf(self, idx):
        '''
        Create a config file for a single minion
        '''
        data = {}
        if self.opts['config_dir']:
            spath = os.path.join(self.opts['config_dir'], 'minion')
            with salt.utils.files.fopen(spath) as conf:
                data = salt.utils.yaml.safe_load(conf) or {}
        minion_id = '{0}-{1}'.format(
                self.opts['name'],
                str(idx).zfill(self.zfill)
                )
        self.minions.append(minion_id)

        dpath = os.path.join(self.swarm_root, minion_id)
        if not os.path.exists(dpath):
            os.makedirs(dpath)

        data.update({
            'id': minion_id,
            'user': self.opts['user'],
            'cachedir': os.path.join(dpath, 'cache'),
            'master': self.opts['master'],
            'log_file': os.path.join(dpath, 'minion.log'),
            'grains': {},
        })

        if self.opts['legion']:
            data.update({
                'legion_fakes': self.opts['legion'],
                'return': 'legion'
            })

        if self.opts['transport'] == 'zeromq':
            minion_pkidir = os.path.join(dpath, 'pki')
            if not os.path.exists(minion_pkidir):
                os.makedirs(minion_pkidir)
                minion_pem = os.path.join(self.pki, 'minion.pem')
                minion_pub = os.path.join(self.pki, 'minion.pub')
                shutil.copy(minion_pem, minion_pkidir)
                shutil.copy(minion_pub, minion_pkidir)
            data['pki_dir'] = minion_pkidir
        elif self.opts['transport'] == 'tcp':
            data['transport'] = 'tcp'

        if self.opts['root_dir']:
            data['root_dir'] = self.opts['root_dir']

        path = os.path.join(dpath, 'minion')

        if self.opts['keep']:
            keep = self.opts['keep'].split(',')
            modpath = os.path.join(os.path.dirname(salt.__file__), 'modules')
            fn_prefixes = (fn_.partition('.')[0] for fn_ in os.listdir(modpath))
            ignore = [fn_prefix for fn_prefix in fn_prefixes if fn_prefix not in keep]
            data['disable_modules'] = ignore

        if self.opts['rand_os']:
            data['grains']['os'] = random.choice(OSES)
        if self.opts['rand_ver']:
            data['grains']['saltversion'] = random.choice(VERS)
        if self.opts['rand_machine_id']:
            data['grains']['machine_id'] = hashlib.md5(minion_id).hexdigest()
        if self.opts['rand_uuid']:
            data['grains']['uuid'] = str(uuid.uuid4())

        with salt.utils.files.fopen(path, 'w+') as fp_:
            salt.utils.yaml.safe_dump(data, fp_)
        self.confs.append({'path': dpath, 'id': minion_id})

    def prep_configs(self):
        '''
        Prepare the confs set
        '''
        for idx in range(self.opts['minions']):
            self.mkconf(idx)


class MasterSwarm(Swarm):
    '''
    Create one or more masters
    '''
    def __init__(self, opts):
        super(MasterSwarm, self).__init__(opts)
        self.conf = os.path.join(self.swarm_root, 'master')

    def start(self):
        '''
        Prep the master start and fire it off
        '''
        # sys.stdout for no newline
        sys.stdout.write('Generating master config...')
        self.mkconf()
        print('done')

        sys.stdout.write('Starting master...')
        self.start_master()
        print('done')

    def start_master(self):
        '''
        Do the master start
        '''
        cmd = 'salt-master -c {0} --pid-file {1}'.format(
                self.conf,
                '{0}.pid'.format(self.conf)
                )
        if self.opts['foreground']:
            cmd += ' -l info &'
        else:
            cmd += ' -d &'
        subprocess.call(cmd, shell=True)

    def mkconf(self):  # pylint: disable=W0221
        '''
        Make a master config and write it'
        '''
        data = {}
        if self.opts['config_dir']:
            spath = os.path.join(self.opts['config_dir'], 'master')
            with salt.utils.files.fopen(spath) as conf:
                data = salt.utils.yaml.safe_load(conf)
        data.update({
            'log_file': os.path.join(self.conf, 'master.log'),
            'open_mode': True  # TODO Pre-seed keys
        })

        os.makedirs(self.conf)
        path = os.path.join(self.conf, 'master')

        with salt.utils.files.fopen(path, 'w+') as fp_:
            salt.utils.yaml.safe_dump(data, fp_)

    def shutdown(self):
        print('Killing master')
        with open(os.devnull, 'w') as stdout:
            subprocess.call(
                'pkill -KILL -f "python.*salt-master"',
                shell=True,
                stdout=stdout,
            )
        print('Master killed')


def main():
    with multiprocessing.Manager() as manager:
        accepted_minions = manager.dict()
        cached = manager.dict()
        event_busser = multiprocessing.Process(
            target=event_listener,
            args=(accepted_minions, cached)
        )
        event_busser.daemon = True
        event_busser.start()

        swarm = Swarm(parse(), accepted_minions, cached)
        try:
            swarm.start()
        finally:
            swarm.shutdown()


# pylint: disable=C0103
if __name__ == '__main__':
    main()
