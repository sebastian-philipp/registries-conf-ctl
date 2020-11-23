from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()


setup(
    name='registries-conf-ctl',
    version='1.0',
    packages=find_packages(),
    url='',
    license='MIT',
    author='Sebastian Wagner',
    author_email='swagner@suse.com',

    description='A CLI tool to modify /etc/registries/registries.conf',
    long_description=long_description,
    long_description_content_type="text/markdown",

    install_requires=[
        'toml',
        'docopt',
    ],

    entry_points = {
        'console_scripts': ['registries-conf-ctl=registries_conf_ctl.cli:main'],
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
    ],
)