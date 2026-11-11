#!/usr/bin/env bash
# Confirma (lendo, nunca escrevendo em /sys) os limites aplicados pelo runtime ao cgroup do conteiner.
set -u
: "${IMAGEM_LAB:?exporte IMAGEM_LAB}"
OUT=resultados/limites; mkdir -p "$OUT"
N=so_a3_lim
trap 'docker rm -f "$N" >/dev/null 2>&1' EXIT
docker run -d --name "$N" --network none --cpus 0.5 --memory 256m --memory-swap 256m --pids-limit 64 "$IMAGEM_LAB" sleep 60 >/dev/null
PID=$(docker inspect -f '{{.State.Pid}}' "$N")
{
  echo "# $(date -Is)"
  docker inspect -f 'Solicitado: NanoCpus={{.HostConfig.NanoCpus}} Memory={{.HostConfig.Memory}} MemorySwap={{.HostConfig.MemorySwap}} PidsLimit={{.HostConfig.PidsLimit}}' "$N"
  CG=$(cut -d: -f3 /proc/"$PID"/cgroup)
  echo "cgroup do conteiner (visao do host): $CG"
  for f in cpu.max memory.max memory.swap.max pids.max; do echo "EFETIVO host  $f = $(cat /sys/fs/cgroup"$CG"/$f 2>&1)"; done
  for f in cpu.max memory.max memory.swap.max pids.max; do echo "EFETIVO dentro $f = $(docker exec "$N" cat /sys/fs/cgroup/$f 2>&1)"; done
  echo "--- cpu.stat"; docker exec "$N" cat /sys/fs/cgroup/cpu.stat
  echo "--- limites ancestrais"
  P="$CG"
  while [ "$P" != "/" ]; do
    P=$(dirname "$P")
    for f in cpu.max memory.max pids.max; do
      [ -r "/sys/fs/cgroup$P/$f" ] && echo "ancestral $P $f = $(cat /sys/fs/cgroup"$P"/$f)"
    done
  done
} | tee "$OUT/limites.txt"
