from setuptools import setup

setup(
    name="legion",
    version_format="{tag}.dev{commitcount}+{gitsha}",
    packages=["legion", "legion/modules", "legion/returners"],
    setup_requires=["setuptools-git-version"],
    entry_points={
        "console_scripts": ["legion=legion.legion:main",],
        "salt.loader": [
            "module_dirs=legion.loader:module_dirs",
            "returner_dirs=legion.loader:returner_dirs",
        ],
    },
)
