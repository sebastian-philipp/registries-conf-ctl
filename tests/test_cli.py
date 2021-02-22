import re

import pytest

from registries_conf_ctl import cli


def test_no_file(fs):
    msg = """
Failed to read configuration:
* [Errno 2] No such file or directory in the fake filesystem: '/etc/containers/registries.conf'
* [Errno 2] No such file or directory in the fake filesystem: '/etc/docker/daemon.json'
""".strip()

    with pytest.raises(cli.CLIError, match=re.escape(msg)):
        cli.run_all({
            '--conf': '/etc/containers/registries.conf,/etc/docker/daemon.json',
            'add-mirror': True,
            '<registry>': 'reg',
            '<mirror>': 'mirr',
            '--insecure': False,
            '--http': False,
            '--docker': False
        })
