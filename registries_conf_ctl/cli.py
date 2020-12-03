"""
registries-conf-ctl. A CLI tool to modify
/etc/registries/registries.conf. Also supports Docker's daemon.json

Usage:
  registries-conf-ctl [options] add-mirror <registry> <mirror> [--insecure] [--http]
  registries-conf-ctl -h | --help
  registries-conf-ctl --version

Options:
  -h --help      Show this screen.
  --version      Show version.
  --conf=<conf>  registries.conf [default: /etc/containers/registries.conf,/etc/docker/daemon.json].
  --insecure     Mark registry as insecure
  --http         HTTP registry mirror (Docker only)
"""
import json
from typing import Dict, Any, cast, TextIO, Optional

import toml
import docopt

class Fmt:
    def add_mirror(self, reg, mirror, insecure, http):
        # type: (str, str, bool, bool) -> None
        raise NotImplementedError

    def dump(self):
        # type: () -> str
        raise NotImplementedError


class RegistriesConfV2(Fmt):
    def __init__(self, f):
        # type: (TextIO) -> None
        self.config = cast(Dict, toml.load(f))
        if 'registries' not in self.config and 'registry' not in self.config:
            raise ValueError('unknown file. maybe empty?')

    def v1_to_v2(self):
        # type: () -> Dict[str, Any]
        if 'registries' not in self.config:
            return self.config

        search = self.config.get('registries', {}).get('search', {}).get('registries', [])
        insecure = self.config.get('registries', {}).get('search', {}).get('insecure', [])
        return {
            'unqualified-search-registries': search,
            'registry': [
                {
                    'prefix': reg,
                    'location': reg,
                    'insecure': reg in insecure,
                    'blocked': False,
                } for reg in search
            ]
        }

    def add_mirror(self, reg, mirror, insecure, http):
        # type: (str, str, bool, bool) -> None
        config = self.v1_to_v2()

        my_regs = [r for r in config['registry'] if r['prefix'] == reg]
        if my_regs:
            my_reg = my_regs[0]
            my_reg['mirror'] = [{
                "location": mirror,
                "insecure": insecure,
            }]
        self.config = config

    def dump(self):
        # type: () -> str
        return toml.dumps(self.config)


def _extend(d, key, what):
    # type: (dict, str, str) -> None
    if key not in d:
        d[key] = [what]
    else:
        d[key].add(what)


class DockerDaemonJson(Fmt):
    def __init__(self, f):
        # type: (TextIO) -> None
        self.config = json.load(f)  # tpe: Dict[str, Any]

    def add_mirror(self, reg, mirror, insecure, http):
        # type: (str, str, bool, bool) -> None
        if reg != 'docker.io':
            raise ValueError("Only mirrors for 'docker.io' are supported")

        proto = 'http' if http else 'https'
        _extend(self.config, 'registry-mirrors', '{proto}://{mirror}'.format(proto=proto, mirror=mirror))
        if insecure:
            _extend(self.config, 'insecure-registries', mirror)

    def dump(self):
        # type: () -> str
        return json.dumps(self.config)


def execute_for_file(fname, arguments):
    # type: (str, dict) -> None
    if arguments['add-mirror']:
        fmt = None  # type: Optional[Fmt]
        e = None
        with open(fname) as f:
            for cls in [DockerDaemonJson, RegistriesConfV2]:
                f.seek(0)
                try:
                    fmt = cls(f)
                    break
                except Exception as ex:
                    e = ex
        if fmt is None:
            raise ValueError("Failed to read {fname}: {e}".format(fname=fname, e=e))

        fmt.add_mirror(arguments['<registry>'], arguments['<mirror>'],
                       arguments['--insecure'], arguments['--http'])

        with open(fname, 'w') as f:
            f.write(fmt.dump())


def main():
    # type: () -> None
    arguments = docopt.docopt(__doc__, version='1.0')

    for fname in arguments['--conf'].split(','):
        execute_for_file(fname, arguments)
