from setuptools import setup

setup(
    name="legion",
    version="1.0.0",
    packages=[
        "legion",
        "legion/modules",
        "legion/returners",
    ],
    entry_points={
        'console_scripts': [
            'legion=legion.legion:main',
        ],
    },
)
