======
Legion
======

The legion tool is used to make more fake minions at a lower cost than can
be done with a minion swarm.

Legion works by telling a minion to just pretend to be many more minions,
it is simple in that the minion still runs the remote execution command
that is sent to it, it just then sends returns for multiple minions back
to the master.

Legion can be used in combination with minionswarm for a double punch of
scale.

Keep in mind that Legion will create a dedicated thundering herd issue.
Since Legion can spoof literally hundreds of thousands of minions on a
single system it can seriously bog down a Salt Master. Make sure that you
are patient starting things up and give your master the time to process
the heavy load.

Run With MinionSwarm
====================

This repo comes with a legion.py script. This script will run a swarm
or minions, with each member of the swarm running a number of fakes, just
clone the repo and run:

python3 legion/legion.py --help

To see all the flags so you can create hordes of minions to test against
with varied grains, versions, and OSes etc.

Setup Dedicated
===============

This repo contains a returner and an execution module. Just activate those
however you want ON THE MINION (I just copy them into the running directory):

cp legion/returners/legion.py /usr/lib/python3.7/site-packages/returners/
cp legion/modules/legion.py /usr/lib/python3.7/site-packages/modules/

Now that those modules are in place open up the minion config and turn
it all on:

legion_fakes: 100
return: legion

Next run a couple of remote ex commands to tell the minion to use legion
to make fake keys and caches:

salt \* legion.keys

Then on the master (unless you turn on open_mode):

salt-key -A

Then activate the caches:

salt \* legion.cache

It will take a while to populate the keys and cache as it is serial and makes
the master do a pillar generation for each minion. Watch the master log
for the storm to pass. But when it is done you can run salt commands to your
heart's delight and get tons of returns:

salt \* network.interfaces
