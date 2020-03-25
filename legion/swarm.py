import hashlib
import logging
import multiprocessing
import multiprocessing.managers
import os
import random
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid

import salt
from salt.config import minion_config
from salt.minion import Minion

from legion.config import OSES, VERS


class Swarm(object):
    """
    Create a swarm of minions
    """

    log = logging.getLogger(__name__)

    def __init__(
        self,
        opts,
        accepted_minions: dict,
        cached_ret: dict,
        manager: multiprocessing.managers.SyncManager,
    ):
        self.accepted_minions = accepted_minions
        self.cached_ret = cached_ret
        self.manager = manager
        self.opts = opts

        # If given a temp_dir, use it for temporary files
        if opts.temp_dir is not None:
            self.swarm_root = os.path.abspath(opts.temp_dir)
        else:
            # If given a root_dir, keep the tmp files there as well
            if opts.root_dir:
                tmpdir = os.path.join(opts.root_dir, "tmp")
            else:
                tmpdir = opts.root_dir
            self.swarm_root = tempfile.mkdtemp(
                prefix="mswarm-root", suffix=".d", dir=tmpdir
            )

        if self.opts.transport == "zeromq":
            self.pki = self._pki_dir()
        self.zfill = len(str(self.opts.minions))

        self.configs = []
        self.minions = []

        random.seed(0)

    def _pki_dir(self):
        """
        Create the shared pki directory
        """
        path = os.path.join(self.swarm_root, "pki")

        if not os.path.exists(path):
            os.makedirs(path)

            self.log.info(f"creating shared pki keys for the swarm at: {path}")

            with open(os.devnull, "w") as stdout:
                subprocess.call(
                    "salt-key -c {0} --gen-keys minion --gen-keys-dir {0} "
                    "--log-file {1} --user {2}".format(
                        path, os.path.join(path, "keys.log"), self.opts.user,
                    ),
                    shell=True,
                    stdout=stdout,
                )
            self.log.info("keys generated")
        return path

    def start(self):
        """
        Start the magic!!
        """
        if self.opts.master_too:
            self.log.info("starting master...")
            master_swarm = MasterSwarm(self.opts)
            master_swarm.start()

        self.log.info("starting minions...")

        minions = MinionSwarm(
            opts=self.opts,
            accepted_minions=self.accepted_minions,
            cached_ret=self.cached_ret,
            manager=self.manager,
        )

        minions.start_minions()

        self.log.info("all {0} minions have started.".format(self.opts.minions))

        while True:
            try:
                time.sleep(5)
            except KeyboardInterrupt:
                self.log.info("shutting down minions")
                self.clean_configs()
                break

    def shutdown(self):
        """
        Tear it all down
        """
        self.log.info("Killing any remaining running minions")
        with open(os.devnull, "w") as stdout:
            subprocess.call(
                'pkill -KILL -f "python.*salt-minion"', shell=True, stdout=stdout,
            )
            if self.opts.master_too:
                self.log.info("Killing any remaining masters")
                subprocess.call(
                    'pkill -KILL -f "python.*salt-master"', shell=True, stdout=stdout,
                )
        if not self.opts.no_clean:
            self.log.info("Remove ALL related temp files/directories")
            shutil.rmtree(self.swarm_root)
        self.log.info("Done")

    def clean_configs(self):
        """
        Clean up the config files
        """
        for conf in self.configs:
            path = conf["path"]
            pidfile = "{0}.pid".format(path)
            try:
                try:
                    with salt.utils.files.fopen(pidfile) as fp_:
                        pid = int(fp_.read().strip())
                    os.kill(pid, signal.SIGTERM)
                except ValueError:
                    pass
                if os.path.exists(pidfile):
                    os.remove(pidfile)
                if not self.opts.no_clean:
                    shutil.rmtree(path)
            except (OSError, IOError):
                pass


class MinionSwarm(Swarm):
    """
    Create minions
    """

    def start_minions(self):
        """
        Iterate over the config files and start up the minions
        """

        self.prep_configs()

        for conf in self.configs:
            minion_id = conf.get("id")

            opts = minion_config(
                path=os.path.join(conf["path"], "minion"), minion_id=minion_id,
            )

            opts["pidfile"] = os.path.join(conf["path"], f"{minion_id}.pid")

            self.log.info(f"starting minion: {minion_id}")

            m = Minion(opts)

            mp = multiprocessing.Process(target=m.tune_in, name=minion_id)
            mp.start()

    def mkconf(self, idx):
        """
        Create a config file for a single minion
        """
        data = {}
        if self.opts.config_dir:
            spath = os.path.join(self.opts.config_dir, "minion")
            with salt.utils.files.fopen(spath) as conf:
                data = salt.utils.yaml.safe_load(conf) or {}

        minion_id = f"{self.opts.name}-{idx + 1:04d}"

        self.minions.append(minion_id)

        dpath = os.path.join(self.swarm_root, minion_id)
        if not os.path.exists(dpath):
            os.makedirs(dpath)

        data.update(
            {
                "id": minion_id,
                "user": self.opts.user,
                "cachedir": os.path.join(dpath, "cache"),
                "master": self.opts.master,
                "log_file": os.path.join(dpath, "minion.log"),
                "grains": {"legion": True},
            }
        )

        if self.opts.legion:
            data.update({"legion_fakes": self.opts.legion, "return": "legion"})

        if self.opts.transport == "zeromq":
            minion_pkidir = os.path.join(dpath, "pki")
            if not os.path.exists(minion_pkidir):
                os.makedirs(minion_pkidir)
                minion_pem = os.path.join(self.pki, "minion.pem")
                minion_pub = os.path.join(self.pki, "minion.pub")
                shutil.copy(minion_pem, minion_pkidir)
                shutil.copy(minion_pub, minion_pkidir)
            data["pki_dir"] = minion_pkidir
        elif self.opts.transport == "tcp":
            data["transport"] = "tcp"

        if self.opts.root_dir:
            data["root_dir"] = self.opts.root_dir

        path = os.path.join(dpath, "minion")

        if self.opts.keep:
            keep = self.opts.keep.split(",")
            modpath = os.path.join(os.path.dirname(salt.__file__), "modules")
            fn_prefixes = (fn_.partition(".")[0] for fn_ in os.listdir(modpath))
            ignore = [fn_prefix for fn_prefix in fn_prefixes if fn_prefix not in keep]
            data["disable_modules"] = ignore

        if self.opts.rand_os:
            data["grains"]["os"] = random.choice(OSES)
        if self.opts.rand_ver:
            data["grains"]["saltversion"] = random.choice(VERS)
        if self.opts.rand_machine_id:
            data["grains"]["machine_id"] = hashlib.md5(minion_id).hexdigest()
        if self.opts.rand_uuid:
            data["grains"]["uuid"] = str(uuid.uuid4())

        with salt.utils.files.fopen(path, "w+") as fp_:
            salt.utils.yaml.safe_dump(data, fp_)
        self.configs.append({"path": dpath, "id": minion_id})

    def prep_configs(self):
        """
        Prepare the configs set
        """
        for idx in range(self.opts.minions):
            self.mkconf(idx)


class MasterSwarm(Swarm):
    """
    Create one or more masters
    """

    def __init__(self, opts):
        super(MasterSwarm, self).__init__(opts)
        self.conf = os.path.join(self.swarm_root, "master")

    def start(self):
        """
        Prep the master start and fire it off
        """
        # sys.stdout for no newline
        sys.stdout.write("Generating master config...")
        self.mkconf()
        self.log.info("done")

        sys.stdout.write("Starting master...")
        self.start_master()
        self.log.info("done")

    def start_master(self):
        """
        Do the master start
        """
        cmd = "salt-master -c {0} --pid-file {1}".format(
            self.conf, "{0}.pid".format(self.conf)
        )
        if self.opts.foreground:
            cmd += " -l info &"
        else:
            cmd += " -d &"
        subprocess.call(cmd, shell=True)

    def mkconf(self):  # pylint: disable=W0221
        """
        Make a master config and write it'
        """
        data = {}
        if self.opts.config_dir:
            spath = os.path.join(self.opts.config_dir, "master")
            with salt.utils.files.fopen(spath) as conf:
                data = salt.utils.yaml.safe_load(conf)
        data.update(
            {
                "log_file": os.path.join(self.conf, "master.log"),
                "open_mode": True,  # TODO Pre-seed keys
            }
        )

        os.makedirs(self.conf)
        path = os.path.join(self.conf, "master")

        with salt.utils.files.fopen(path, "w+") as fp_:
            salt.utils.yaml.safe_dump(data, fp_)

    def shutdown(self):
        self.log.info("Killing master")
        with open(os.devnull, "w") as stdout:
            subprocess.call(
                'pkill -KILL -f "python.*salt-master"', shell=True, stdout=stdout,
            )
        self.log.info("Master killed")
