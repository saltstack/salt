# 5-master salt cluster (docker)

Five salt-master containers in a Raft cluster + 5 minions, each subscribed to
all five masters via `master_type: failover`. Shared `cluster_pki_dir` on a
named docker volume. Intended as a harness for cluster scenario testing.

## Layout

- `docker-compose.yml` — 5 masters (`salt-master-{1..5}`) + 5 minions (`salt-minion-{1..5}`)
- `master-1.conf` … `master-5.conf` — per-master config; each lists the other four as `cluster_peers`
- `minion.conf` — failover config pointing at all 5 masters
- `srv/salt/` — minimal state tree
- `smoke.sh` — bring up + wait for Raft leader + `salt '*' test.ping`

## Quick start

```bash
cd tests/monitoring/cluster-5node
docker compose build
docker compose up -d
./smoke.sh
```

## Notes

- Dockerfile is reused from `../Dockerfile.salt`; build context is the repo root.
- `cluster_pki_dir` is `/etc/salt/cluster-pki` on a named volume `cluster-pki` shared by all masters.
- `cache_dir` is NOT shared — each master has its own.
- All masters bind `ret_port=44506` / `publish_port=44505` on their own container IP.
  Minions reach them by service name (`salt-master-1` … `salt-master-5`).
