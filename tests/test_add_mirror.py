import subprocess

import toml

from registries_conf_ctl import cli

v1 = """
[registries.search]
registries = ['registry.access.redhat.com', 'registry.redhat.io', 'docker.io', 'quay.io']

[registries.insecure]
registries = []
"""

v2 = """
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

expected = {
    'unqualified-search-registries': ['registry.access.redhat.com', 'registry.redhat.io',
                                      'docker.io', 'quay.io'],
    'registry': [
        {'prefix': 'registry.access.redhat.com',
         'location': 'registry.access.redhat.com',
         'insecure': False,
         'blocked': False},
        {'prefix': 'registry.redhat.io',
         'location': 'registry.redhat.io',
         'insecure': False,
         'blocked': False},
        {'prefix': 'docker.io',
         'location': 'docker.io',
         'insecure': False,
         'blocked': False,
         'mirror': [{'location': 'vossi04.front.sepia.ceph.com:5000',
                     'insecure': True}]},
        {'prefix': 'quay.io',
         'location': 'quay.io',
         'insecure': False,
         'blocked': False}
    ]
}

def test_add_mirror():
    assert cli.registries_add_mirror_to_registry(toml.loads(v1), 'docker.io', 'vossi04.front.sepia.ceph.com:5000', True) == expected
    assert cli.registries_add_mirror_to_registry(toml.loads(v2), 'docker.io', 'vossi04.front.sepia.ceph.com:5000', True) == expected


def test_add_mirror_cli(tmpdir):
    p = tmpdir.join("conf.conf")
    p.write(v2)

    subprocess.check_call(f'registries-conf-ctl --conf {p} add-mirror docker.io vossi04 --insecure', shell=True)

    with open('/tmp/foo.conf', 'w') as f:
        f.write(p.read())

    assert 'vossi04' in p.read()