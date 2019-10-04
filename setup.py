from setuptools import setup

setup(
    name="legion",
    version="1.0.2",
    packages=[
        "legion",
        "legion/modules",
        "legion/returners",
    ],
    entry_points={
        'console_scripts': [
            'legion=legion.legion:main',
        ],
        'salt.loader': [
            'module_dirs=legion.loader:module_dirs',
            'returner_dirs=legion.loader:returner_dirs',
        ],
    },
)
