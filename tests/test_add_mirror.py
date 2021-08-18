import subprocess
from io import StringIO

import pytest

from registries_conf_ctl import cli

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

[[registry.mirror]]
location = "vossi04.front.sepia.ceph.com:5000"
insecure = true

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
    ]
}

docker_in = u"""
{
    "something": 1
}
"""


docker_out = {
    "something": 1,
    "insecure-registries": ["vossi04.front.sepia.ceph.com:5000"],
    "registry-mirrors": ["http://vossi04.front.sepia.ceph.com:5000"]
}


@pytest.mark.parametrize("test_input,expected,cls", [
    (v1, reg_expected, cli.RegistriesConfV2),
    (v1, reg_expected, cli.RegistriesConfV2),
    (docker_in, docker_out, cli.DockerDaemonJson),
])
def test_add_mirror(test_input, expected, cls, tmpdir):
    fmt = cls(StringIO(test_input))
    fmt.add_mirror('docker.io', 'vossi04.front.sepia.ceph.com:5000', True, True)
    assert fmt.dump_json() == expected

    d = '--docker' if cls is cli.DockerDaemonJson else ''

    p = tmpdir.join("conf.conf")
    p.write(test_input)

    assert subprocess.check_output('registries-conf-ctl --conf {p} {d} list-mirrors docker.io'.format(p=p,d=d), shell=True) == b'\n'

    subprocess.check_call('registries-conf-ctl --conf {p} {d} add-mirror docker.io vossi04.front.sepia.ceph.com:5000 --insecure --http'.format(p=p,d=d), shell=True)

    assert cls(p).dump_json() == expected

    subprocess.check_call('registries-conf-ctl --conf {p} {d} add-mirror docker.io vossi04.front.sepia.ceph.com:5000 --insecure --http'.format(p=p,d=d), shell=True)

    assert cls(p).dump_json() == expected

    assert subprocess.check_output('registries-conf-ctl --conf {p} {d} list-mirrors docker.io'.format(p=p,d=d), shell=True) == b'vossi04.front.sepia.ceph.com:5000\n'


def test_small_registries_conf():
    s = u"""unqualified-search-registries = ["registry.fedoraproject.org", "registry.access.redhat.com", "registry.centos.org", "docker.io"]"""

    fmt = cli.RegistriesConfV2(StringIO(s))

    fmt.add_mirror('docker.io', 'vossi04.front.sepia.ceph.com:5000', True, True)

    assert fmt.dump_json() == {
        'unqualified-search-registries': [
            'docker.io',
            'registry.access.redhat.com',
            'registry.centos.org',
            'registry.fedoraproject.org',
        ],
        'registry': [
            {
                'location': 'docker.io',
                'prefix': 'docker.io',
                'mirror': [
                    {
                        'insecure': True,
                        'location': 'vossi04.front.sepia.ceph.com:5000'
                    }
                ],
            }
        ]
    }


