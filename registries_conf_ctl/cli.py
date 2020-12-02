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

from typing import Dict, Any, cast, TextIO

import toml
import docopt



class RegistriesConfV2:
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

    def add_mirror(self, reg: str, mirror: str, insecure: bool) -> Dict[str, Any]:
        config = self.v1_to_v2()

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

    if arguments['add-mirror']:
        with open(registries_conf) as f:
            out = RegistriesConfV2(f).add_mirror(arguments['<registry>'], arguments['<mirror>'], arguments['--insecure'])

        with open(registries_conf, 'w') as f:
            f.write(toml.dumps(out))

