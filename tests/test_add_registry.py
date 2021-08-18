import subprocess
from io import StringIO

import pytest

from registries_conf_ctl import cli

v1_empty = u"""
[registries.search]
registries = []
"""

v1 = u"""
[registries.search]
registries = ['registry.access.redhat.com', 'registry.redhat.io', 'docker.io', 'quay.io']

[registries.insecure]
registries = []
"""

v2 = u"""
unqualified-search-registries = ["registry.access.redhat.com", "registry.redhat.io", "docker.io", 'quay.io']

[[registry]]
prefix = "registry.access.redhat.com"
location = "registry.access.redhat.com"
insecure = false
blocked = false

[[registry]]
prefix = "registry.redhat.io"
location = "registry.redhat.io"
insecure = false
blocked = false

[[registry]]
prefix = "docker.io"
location = "docker.io"
insecure = false
blocked = false

[[registry]]
prefix = "quay.io"
location = "quay.io"
insecure = false
blocked = false
"""

reg_expected = {
    'unqualified-search-registries': ['docker.io', 'quay.io', 'registry.access.redhat.com', 'registry.redhat.io'],
    'registry': [
        {'prefix': 'docker.io',
         'location': 'docker.io',
         'mirror': [{'location': 'vossi04.front.sepia.ceph.com:5000',
                     'insecure': True}]},
        {'prefix': 'localhost',
         'location': 'localhost',
         'insecure': True},
    ]
}


docker_in = u"""
{
    "something": 1
}
"""


docker_out = {
    "something": 1,
    "insecure-registries": ["localhost", "vossi04.front.sepia.ceph.com:5000"],
    "registry-mirrors": ["http://vossi04.front.sepia.ceph.com:5000"]
}


def test_add_registry_simple():
    fmt = cli.RegistriesConfV2(StringIO(v1_empty))
    fmt.add_registry('localhost', '', True, False)
    assert fmt.dump_json() == {
        'registry': [
            {'prefix': 'localhost',
             'location': 'localhost',
             'insecure': True}
        ]
    }


def test_add_registry_search():
    fmt = cli.RegistriesConfV2(StringIO(v1_empty))
    fmt.add_registry('localhost', '', True, True)
    assert fmt.dump_json() == {
        'unqualified-search-registries': ['localhost'],
        'registry': [
            {'prefix': 'localhost',
             'location': 'localhost',
             'insecure': True}
        ]
    }

def test_unqualified_search_registries():
    s = u"""unqualified-search-registries = ["registry.fedoraproject.org", "registry.access.redhat.com", "registry.centos.org", "docker.io"]"""

    fmt = cli.RegistriesConfV2(StringIO(s))
    print(fmt.config)
    assert fmt.dump_json() == {
        'unqualified-search-registries': [
            'docker.io',
            'registry.access.redhat.com',
            'registry.centos.org',
            'registry.fedoraproject.org',
        ]
    }


@pytest.mark.parametrize("test_input,expected,cls", [
    (v1, reg_expected, cli.RegistriesConfV2),
    (v2, reg_expected, cli.RegistriesConfV2),
    (v1_empty, reg_expected, cli.RegistriesConfV2),
    (docker_in, docker_out, cli.DockerDaemonJson),
])
def test_add_registry(test_input, expected, cls, tmpdir):
    fmt = cls(StringIO(test_input))
    fmt.add_registry('registry.access.redhat.com', '', False, True)
    fmt.add_registry('registry.redhat.io', '', False, True)
    fmt.add_registry('docker.io', '', False, True)
    fmt.add_registry('quay.io', '', False, True)
    fmt.add_registry('localhost', '', True, False)
    fmt.add_mirror('docker.io', 'vossi04.front.sepia.ceph.com:5000', True, True)

    assert fmt.dump_json() == expected
