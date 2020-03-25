#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
The minionswarm script will start a group of salt minions with different ids
on a single system to test scale capabilities
"""
import logging
import multiprocessing
import time
import warnings

# Import salt libs
import salt
import salt.config
import salt.modules
import salt.returners
import salt.utils.event
import salt.utils.files
import salt.utils.platform
import salt.utils.yaml

from legion.config import parse
from legion.swarm import Swarm

if salt.utils.platform.is_windows():
    import salt.utils.win_functions
else:
    pass


def event_listener(accepted_minions, cached_ret):
    opts = salt.config.client_config("/etc/salt/master")
    event = salt.utils.event.get_event(
        "master", sock_dir=opts["sock_dir"], transport=opts["transport"], opts=opts
    )

    while 1:
        data = event.get_event()
        if data:
            if "act" in data:
                mid = data["id"]
                if mid not in accepted_minions:
                    accepted_minions[mid] = True

            elif "return" in data and "fun" in data and data["fun"] == "legion.cache":
                mid = data["id"]
                if mid not in cached_ret:
                    cached_ret[mid] = True

        time.sleep(0.1)


def main():
    warnings.filterwarnings(action="ignore", category=DeprecationWarning)

    log = logging.getLogger(__name__)

    opts, args = parse()

    log.info("starting manager")

    with multiprocessing.Manager() as manager:
        accepted_minions = manager.dict()
        cached = manager.dict()
        event_busser = multiprocessing.Process(
            target=event_listener, args=(accepted_minions, cached), daemon=True
        )
        event_busser.start()

        swarm = Swarm(
            opts=opts,
            accepted_minions=accepted_minions,
            cached_ret=cached,
            manager=manager,
        )

        try:
            swarm.start()
        finally:
            swarm.shutdown()
