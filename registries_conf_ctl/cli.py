"""
registries-conf-ctl. A CLI tool to modify /etc/registries/registries.conf.

Usage:
  registries-conf-ctl [options] add-mirror <registry> <mirror> [--insecure]
  registries-conf-ctl -h | --help
  registries-conf-ctl --version

Options:
  -h --help      Show this screen.
  --version      Show version.
  --conf=<conf>  registries.conf [default: /etc/containers/registries.conf].
  --insecure     Mark registry as insecure

"""

from typing import Dict, Any, cast

import toml
import docopt


def v1_to_v2(config: Dict[str, Any]) -> Dict[str, Any]:
    if 'registries' not in config:
        return config

    search = config.get('registries', {}).get('search', {}).get('registries', [])
    insecure = config.get('registries', {}).get('search', {}).get('insecure', [])
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


def registries_add_mirror_to_registry(conf: Dict[str, Any], reg: str, mirror: str, insecure: bool) -> Dict[str, Any]:
    config = v1_to_v2(conf)

    my_regs = [r for r in config['registry'] if r['prefix'] == reg]
    if my_regs:
        my_reg = my_regs[0]
        my_reg['mirror'] = [{
            "location": mirror,
            "insecure": insecure,
        }]
    return config


def main() -> None:
    arguments = docopt.docopt(__doc__, version='1.0')

    registries_conf = arguments['--conf']

    with open(registries_conf) as f:
        config = cast(Dict, toml.load(f))

    if arguments['add-mirror']:
        out = registries_add_mirror_to_registry(config, arguments['<registry>'], arguments['<mirror>'], arguments['--insecure'])

        with open(registries_conf, 'w') as f:
            f.write(toml.dumps(out))

