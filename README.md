# registries-conf-ctl

registries-conf-ctl. A CLI tool to modify
/etc/registries/registries.conf. Also supports Docker's daemon.json

```
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
```

# Q & A

### If `docker` and `podman` commands are both detected, will the tool modify both config files?

yes.

### What if neither are detected?

It will fail.

### Will it create the files?

no.