"""
registries-conf-ctl. A CLI tool to modify
/etc/registries/registries.conf. Also supports Docker's daemon.json

Usage:
  registries-conf-ctl [options] add-mirror <registry> <mirror> [--insecure] [--http]
  registries-conf-ctl [options] list-mirrors <registry>
  registries-conf-ctl -h | --help
  registries-conf-ctl --version

Options:
  -h --help      Show this screen.
  --version      Show version.
  --conf=<conf>  registries.conf [default: /etc/containers/registries.conf,/etc/docker/daemon.json].
  --docker       Treat `--conf` as a docker config file
  --insecure     Mark registry as insecure
  --http         HTTP registry mirror (Docker only)
"""
import json
from typing import Dict, Any, cast, TextIO, TypeVar, Iterable, Callable, List, Type

T = TypeVar('T')
U = TypeVar('U')

import toml
import docopt


class Fmt:
    def add_mirror(self, reg, mirror, insecure, http):
        # type: (str, str, bool, bool) -> None
        raise NotImplementedError

    def list_mirrors(self, reg):
        # type: (str) -> Iterable[str]
        raise NotImplementedError


    def dump(self):
        # type: () -> str
        raise NotImplementedError


class RegistriesConfV2(Fmt):
    def __init__(self, f):
        # type: (TextIO) -> None
        self.config = cast(Dict, toml.load(f))
        if not self.config:
            raise ValueError('empty file')

        if 'registries' not in self.config and \
                'registry' not in self.config and \
                'unqualified-search-registries' not in self.config:
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

        my_regs = [r for r in config.get('registry', []) if r['prefix'] == reg]
        if not my_regs and reg in config['unqualified-search-registries']:
            if 'registry' not in config:
                config['registry'] = []
            config['registry'].append(
                {
                    'prefix': reg,
                    'location': reg,
                }
            )
            my_regs = [r for r in config['registry'] if r['prefix'] == reg]
        if my_regs:
            my_reg = my_regs[0]
            my_reg['mirror'] = [{
                "location": mirror,
                "insecure": insecure,
            }]
            self.config = config

    def list_mirrors(self, reg):
        # type: (str) -> Iterable[str]
        config = self.v1_to_v2()

        my_regs = [r for r in config['registry'] if r['prefix'] == reg]
        if my_regs:
            my_reg = my_regs[0]
            if 'mirror' in my_reg and my_reg['mirror']:
                for m in my_reg['mirror']:
                    yield m['location']

    def dump(self):
        # type: () -> str
        return toml.dumps(self.config)


def _extend(d, key, what):
    # type: (dict, str, str) -> None
    if key not in d:
        d[key] = [what]
    else:
        d[key] = list(set(d[key] + [what]))


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

    def list_mirrors(self, reg):
        # type: (str) -> Iterable[str]

        if reg == 'docker.io':
            for m in self.config.get('registry-mirrors', []):
                yield m.lstrip('http://').lstrip('https://')

    def dump(self):
        # type: () -> str
        return json.dumps(self.config)


def _raise_if_all_fail(l, f, what):
    # type: (Iterable[T], Callable[[T], U], str) -> U
    es = []  # type: List[Exception]
    for el in l:
        try:
            return f(el)
        except Exception as ex:
            es.append(ex)
    details = '\n'.join('* {e}'.format(e=e) for e in es)
    raise ValueError('{what}:\n{details}'.format(what=what,details=details))


def execute_for_file(fname, arguments):
    # type: (str, dict) -> None
    if arguments['--docker']:
        conf_type = DockerDaemonJson  # type: Type[Fmt]
    else:
        conf_type = {
            '/etc/docker/daemon.json': DockerDaemonJson
        }.get(fname, RegistriesConfV2)

    if arguments['add-mirror']:
        with open(fname) as f:
            def fun(cls):
                # type: (Any) -> Any
                f.seek(0)
                return cls(f)
            fmt = fun(conf_type)

        fmt.add_mirror(arguments['<registry>'], arguments['<mirror>'],
                       arguments['--insecure'], arguments['--http'])

        with open(fname, 'w') as f:
            f.write(fmt.dump())
    if arguments['list-mirrors']:
        with open(fname) as f:
            def fun(cls):
                # type: (Any) -> Any
                f.seek(0)
                return cls(f)
            fmt = _raise_if_all_fail([DockerDaemonJson, RegistriesConfV2],
                                     fun,
                                     "Failed to read {fname}".format(fname=fname))

        print('\n'.join(fmt.list_mirrors(arguments['<registry>'])))


def run_all(arguments):
    # type: (dict) -> None
    _raise_if_all_fail(arguments['--conf'].split(','),
                       lambda fname: execute_for_file(fname, arguments),
                       'Failed to read configuration')


def main():
    # type: () -> None
    arguments = docopt.docopt(__doc__, version='1.0')
    run_all(arguments)

