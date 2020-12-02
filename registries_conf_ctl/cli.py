"""
registries-conf-ctl. A CLI tool to modify /etc/registries/registries.conf.

Usage:
  registries-conf-ctl [options] add-mirror <registry> <mirror> [--insecure] [--http]
  registries-conf-ctl -h | --help
  registries-conf-ctl --version

Options:
  -h --help      Show this screen.
  --version      Show version.
  --conf=<conf>  registries.conf [default: /etc/containers/registries.conf].
  --insecure     Mark registry as insecure
  --http         HTTP registry mirror (Docker only)

"""
import json
from typing import Dict, Any, cast, TextIO, Optional

import toml
import docopt

class Fmt:
    def add_mirror(self, reg: str, mirror: str, insecure: bool, http: bool) -> None:
        raise NotImplementedError

    def dump(self) -> str:
        raise NotImplementedError


class RegistriesConfV2(Fmt):
    def __init__(self, f: TextIO):
        self.config = cast(Dict, toml.load(f))
        if 'registries' not in self.config and 'registry' not in self.config:
            raise ValueError('unknown file. maybe empty?')

    def v1_to_v2(self) -> Dict[str, Any]:
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

    def add_mirror(self, reg: str, mirror: str, insecure: bool, http: bool) -> None:
        config = self.v1_to_v2()

        my_regs = [r for r in config['registry'] if r['prefix'] == reg]
        if my_regs:
            my_reg = my_regs[0]
            my_reg['mirror'] = [{
                "location": mirror,
                "insecure": insecure,
            }]
        self.config = config

    def dump(self) -> str:
        return toml.dumps(self.config)


def _extend(d: dict, key: str, what: str) -> None:
    if key not in d:
        d[key] = [what]
    else:
        d[key].add(what)


class DockerDaemonJson(Fmt):
    def __init__(self, f: TextIO):
        self.config: Dict[str, Any] = json.load(f)

    def add_mirror(self, reg: str, mirror: str, insecure: bool, http: bool) -> None:
        if reg != 'docker.io':
            raise ValueError("Only mirrors for 'docker.io' are supported")

        proto = 'http' if http else 'https'
        _extend(self.config, 'registry-mirrors', f'{proto}://{mirror}')
        if insecure:
            _extend(self.config, 'insecure-registries', mirror)

    def dump(self) -> str:
        return json.dumps(self.config)


def main() -> None:
    arguments = docopt.docopt(__doc__, version='1.0')

    registries_conf = arguments['--conf']

    if arguments['add-mirror']:
        fmt: Optional[Fmt] = None
        e = None
        with open(registries_conf) as f:
            for cls in [DockerDaemonJson, RegistriesConfV2]:
                f.seek(0)
                try:
                    fmt = cls(f)
                    break
                except Exception as ex:
                    e = ex
        if fmt is None:
            raise ValueError(f"Failed to read {registries_conf}: {e}")

        fmt.add_mirror(arguments['<registry>'], arguments['<mirror>'],
                       arguments['--insecure'], arguments['--http'])

        with open(registries_conf, 'w') as f:
            f.write(fmt.dump())

