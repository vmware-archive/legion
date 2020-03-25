import optparse
import os
import pwd

import salt

OSES = [
    "Arch",
    "Ubuntu",
    "Debian",
    "CentOS",
    "Fedora",
    "Gentoo",
    "AIX",
    "Solaris",
]

VERS = [
    "2014.1.6",
    "2014.7.4",
    "2015.5.5",
    "2015.8.0",
]


def this_user():
    """
    Get the user associated with the current process.
    """
    if salt.utils.platform.is_windows():
        return salt.utils.win_functions.get_current_user(with_domain=False)
    return pwd.getpwuid(os.getuid())[0]


def parse():
    """
    Parse the cli options
    """
    parser = optparse.OptionParser()
    parser.add_option(
        "-l",
        "--legion",
        dest="legion",
        default=0,
        type="int",
        help="The number of extra legion fakes",
    )
    parser.add_option(
        "-m",
        "--minions",
        dest="minions",
        default=5,
        type="int",
        help="The number of minions to make",
    )
    parser.add_option(
        "-M",
        action="store_true",
        dest="master_too",
        default=False,
        help="Run a local master and tell the minions to connect to it",
    )
    parser.add_option(
        "--master",
        dest="master",
        default="salt",
        help="The location of the salt master that this swarm will serve",
    )
    parser.add_option(
        "--name",
        "-n",
        dest="name",
        default="ms",
        help=(
            "Give the minions an alternative id prefix, this is used "
            "when minions from many systems are being aggregated onto "
            "a single master"
        ),
    )
    parser.add_option(
        "--rand-os",
        dest="rand_os",
        default=False,
        action="store_true",
        help="Each Minion claims a different os grain",
    )
    parser.add_option(
        "--rand-ver",
        dest="rand_ver",
        default=False,
        action="store_true",
        help="Each Minion claims a different version grain",
    )
    parser.add_option(
        "--rand-machine-id",
        dest="rand_machine_id",
        default=False,
        action="store_true",
        help="Each Minion claims a different machine id grain",
    )
    parser.add_option(
        "--rand-uuid",
        dest="rand_uuid",
        default=False,
        action="store_true",
        help="Each Minion claims a different UUID grain",
    )
    parser.add_option(
        "-k",
        "--keep-modules",
        dest="keep",
        default="",
        help="A comma delimited list of modules to enable",
    )
    parser.add_option(
        "-f",
        "--foreground",
        dest="foreground",
        default=False,
        action="store_true",
        help="Run the minions with debug output of the swarm going to the terminal",
    )
    parser.add_option(
        "--temp-dir",
        dest="temp_dir",
        default=None,
        help="Place temporary files/directories here",
    )
    parser.add_option(
        "--no-clean",
        action="store_true",
        default=False,
        help="Don't cleanup temporary files/directories",
    )
    parser.add_option(
        "--root-dir",
        dest="root_dir",
        default=None,
        help="Override the minion root_dir config",
    )
    parser.add_option(
        "--transport",
        dest="transport",
        default="zeromq",
        help="Declare which transport to use, default is zeromq",
    )
    parser.add_option(
        "--start-delay",
        dest="start_delay",
        default=0.0,
        type="float",
        help="Seconds to wait between minion starts",
    )
    parser.add_option(
        "--legion-start-delay",
        dest="legion_start_delay",
        default=0.0,
        type="float",
        help="Seconds to wait to issue legion commands",
    )
    parser.add_option(
        "-c",
        "--config-dir",
        default="",
        help="Pass in a configuration directory containing base configuration.",
    )
    parser.add_option(
        "-u", "--user", help="the user to run Legion as", default=this_user()
    )
    parser.add_option(
        "--run-modules",
        help=(
            "Call legion.keys and legion.cache modules as minions start. "
            "This requires legion to be ran on the salt master that they "
            "are connecting to."
        ),
        dest="run_modules",
        action="store_true",
        default=False,
    )

    parser.add_option(
        "--wait",
        action="store_true",
        default=False,
        help="Wait for minion key to be accepted before proceeding onto the next",
    )

    return parser.parse_args()
