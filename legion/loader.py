import os

PKG_DIR = os.path.abspath(os.path.dirname(__file__))


def returner_dirs():
    """
    yield one path per parent directory of where returner modules can be found
    """
    yield os.path.join(PKG_DIR, "returners")


def module_dirs():
    """
    yield one path per parent directory of where execution modules can be found
    """
    yield os.path.join(PKG_DIR, "modules")
