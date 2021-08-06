"""
registries-conf-ctl. A CLI tool to modify
/etc/registries/registries.conf. Also supports Docker's daemon.json

Usage:
  registries-conf-ctl [options] add-mirror <registry> <mirror> [--insecure] [--http]
  registries-conf-ctl [options] list-mirrors <registry>
  registries-conf-ctl [options] add-registry <registry> [--location=location] [--insecure] [--unqualified-search]
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
from __future__ import print_function

import sys
from collections import namedtuple

import json
from typing import Dict, Any, cast, TextIO, TypeVar, Iterable, Callable, List, Type

T = TypeVar('T')
U = TypeVar('U')
K = TypeVar('K', bound=type)

import toml
import docopt


def default_factory(**factory_kw):
    # type: (Callable) -> Callable[[K], K]
    # https://stackoverflow.com/a/68682382/3185053
    def wrapper(cls):
        # type: (K) -> K
        def init(*args, **kwargs):
            # type: (Any, Any) -> Any
            for key, factory in factory_kw.items():
                if key not in kwargs:
                    kwargs[key] = factory()
            return cls(*args, **kwargs)

        classmethods = [attr for attr, obj in vars(cls).items() if isinstance(obj, classmethod)]
        for clsm in classmethods:
            def cls_m_wrapper(*args, **kwargs):
                # type: (Any, Any) -> Any
                return getattr(cls, clsm)(*args, **kwargs)
            setattr(init, clsm, cls_m_wrapper)
        return cast(K, init)
    return wrapper


class CLIError(Exception):
    pass


@default_factory(insecure=lambda : False, http=lambda: False)
class Mirror(namedtuple('Mirror', 'location insecure http')):

    def to_json_v2(self):
        # type: () -> dict
        r = {
            'location': self.location,
        } # type: dict
        if self.insecure:
            r['insecure'] = self.insecure
        return r

    @classmethod
    def from_docker(cls, mirror):
        # type: (str) -> Mirror
        location = mirror.lstrip('http://').lstrip('https://')
        if mirror.startswith('http://'):
            return cls(location=location, insecure=False, http=True)
        return cls(location=location, insecure=False, http=False)

    def to_docker(self):
        # type: () -> str
        proto = 'http' if self.http else 'https'
        return '{proto}://{mirror}'.format(proto=proto, mirror=self.location)


@default_factory(insecure=lambda: False, blocked=lambda: False, mirror=dict, unqualified_search=lambda: False)
class Reg(namedtuple('Reg', 'prefix location insecure blocked mirror unqualified_search')):

    def to_json_v2(self):
        # type: () -> dict
        r = {
            'prefix': self.prefix,
            'location': self.location,
        }  # type: dict
        if self.insecure:
            r['insecure'] = self.insecure
        if self.blocked:
            r['blocked'] = self.blocked
        if self.mirror:
            r['mirror'] = [m.to_json_v2() for m in self.mirror.values()]
        return r

    def should_emit_v2(self):
        # type: () -> bool
        if self.location != self.prefix:
            return True
        if self.insecure:
            return True
        if self.blocked:
            return True
        if self.mirror:
            return True
        return False


class Fmt(object):
    def __init__(self, config):
        # type: (Dict[str, Reg]) -> None
        self.config = config

    def add_mirror(self, reg, mirror, insecure, http):
        # type: (str, str, bool, bool) -> None

        if isinstance(self, DockerDaemonJson) and reg != 'docker.io':
            raise CLIError("Only mirrors for 'docker.io' are supported")

        if reg not in self.config:
            self.config[reg] = Reg(  # type: ignore
                prefix=reg,
                location=reg,
            )

        if mirror not in self.config[reg].mirror:
            self.config[reg].mirror[mirror] = Mirror(mirror)  # type: ignore

        self.config[reg].mirror[mirror] = self.config[reg].mirror[mirror]._replace(insecure=insecure)
        self.config[reg].mirror[mirror] = self.config[reg].mirror[mirror]._replace(http=http)

    def list_mirrors(self, reg):
        # type: (str) -> Iterable[str]

        if reg in self.config:
            for m in self.config[reg].mirror.values():
                yield m.location

    def add_registry(self, reg, location, insecure, unqualified_search):
        # type: (str, str, bool, bool) -> None
        location = location or reg
        if reg not in self.config:
            self.config[reg] = Reg(reg, location)  # type: ignore

        self.config[reg] = self.config[reg]._replace(insecure=insecure)
        self.config[reg] = self.config[reg]._replace(location=location)
        self.config[reg] = self.config[reg]._replace(unqualified_search=unqualified_search)

    def dump_json(self):
        # type: () -> dict
        raise NotImplementedError

    def dump(self):
        # type: () -> str
        raise NotImplementedError


class RegistriesConfV2(Fmt):

    def __init__(self, f):
        # type: (TextIO) -> None
        config = cast(Dict, toml.load(f))
        if not config:
            raise CLIError('Failed to load {f}: empty file'.format(f=f.name))

        if 'registries' not in config and \
                'registry' not in config and \
                'unqualified-search-registries' not in config:
            raise CLIError('Failed to load {f}: unknown file'.format(f=f.name))
        super(RegistriesConfV2, self).__init__(self.v1_to_v2(config))

    def v1_to_v2(self, config):
        # type: (dict) -> Dict[str, Reg]
        if 'registries' not in config:  # is_v2:
            search = config['unqualified-search-registries']
            ret = {
                reg['prefix']: Reg(prefix=reg['prefix'],
                    location=reg.get('location', reg['prefix']),
                    insecure=reg.get('insecure', False),
                    blocked=reg.get('blocked', False),
                    mirror={m['location']: Mirror(**m) for m in reg.get('mirror', [])},
                    unqualified_search=reg in search)
                for reg in config.get('registry', [])
            }
            for s in search:
                if s not in ret:
                    ret[s] = Reg(  # type: ignore
                        prefix=s,
                        location=s,
                        unqualified_search=True
                    )
                else:
                    ret[s] = ret[s]._replace(unqualified_search=True)
            return ret
        # v1
        search = config.get('registries', {}).get('search', {}).get('registries', [])
        insecure = config.get('registries', {}).get('insecure', {}).get('registries', [])
        return {reg: Reg(prefix=reg,
                         location=reg,
                         insecure=reg in insecure,
                         blocked=False,
                         mirror={},
                         unqualified_search=reg in search) for reg in set(search + insecure)}

    def dump_json(self):
        # type: () -> dict

        ret = {}  # type: dict

        search = list(sorted(r.location for r in self.config.values() if r.unqualified_search))
        if search:
            ret['unqualified-search-registries'] = search
        regs = [reg.to_json_v2() for reg in sorted(self.config.values(), key=lambda r: r.prefix) if reg.should_emit_v2()]
        if regs:
            ret['registry'] = regs
        return ret

    def dump(self):
        # type: () -> str
        return toml.dumps(self.dump_json())


class DockerDaemonJson(Fmt):
    def __init__(self, f):
        # type: (TextIO) -> None
        self.docker_config = json.load(f)  # type: Dict[str, Any]

        regs = {
            r: Reg(
                prefix=r,
                location=r,
                insecure=True,
            ) for r in self.docker_config.get('insecure-registries', [])  # type: ignore
        }
        if 'docker.io' not in regs:
            regs['docker.io'] = Reg('docker.io', 'docker.io')  # type: ignore

        regs['docker.io'] = regs['docker.io']._replace(mirror={m: Mirror.from_docker(m) for m in self.docker_config.get('registry-mirrors', [])})
        super(DockerDaemonJson, self).__init__(regs)

    def dump_json(self):
        # type: () -> dict
        insec_regs = [r.prefix for r in self.config.values() if r.insecure]
        insec_mirrors = [m.location for m in self.config['docker.io'].mirror.values() if m.insecure]
        self.docker_config['insecure-registries'] = list(sorted(set(insec_regs + insec_mirrors)))
        self.docker_config['registry-mirrors'] = list(sorted(m.to_docker() for m in self.config['docker.io'].mirror.values()))
        return self.docker_config

    def dump(self):
        # type: () -> str
        return json.dumps(self.dump_json())


def _raise_if_all_fail(l, f, what):
    # type: (Iterable[T], Callable[[T], U], str) -> U
    es = []  # type: List[Exception]
    for el in l:
        try:
            return f(el)
        except Exception as ex:
            es.append(ex)
    details = '\n'.join('* {e}'.format(e=e) for e in es)
    raise CLIError('{what}:\n{details}'.format(what=what,details=details))


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
    if arguments['add-registry']:
        with open(fname) as f:
            def fun(cls):
                # type: (Any) -> Any
                f.seek(0)
                return cls(f)

            fmt = fun(conf_type)
        fmt.add_registry(arguments['<registry>'], arguments['--location'],
                         arguments['--insecure'], arguments['--unqualified-search'])

        with open(fname, 'w') as f:
            f.write(fmt.dump())


def run_all(arguments):
    # type: (dict) -> None
    _raise_if_all_fail(arguments['--conf'].split(','),
                       lambda fname: execute_for_file(fname, arguments),
                       'Failed to read configuration')


def main():
    # type: () -> int
    arguments = docopt.docopt(__doc__, version='1.0')
    try:
        run_all(arguments)
        return 0
    except CLIError as e:
        print(str(e), file=sys.stderr)
        return 1

