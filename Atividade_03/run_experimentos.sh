#!/usr/bin/env bash
# Uso: export IMAGEM_LAB=...; export ITERACOES=...; bash run_experimentos.sh
set -u
: "${IMAGEM_LAB:?exporte IMAGEM_LAB (Parte A)}"
: "${ITERACOES:?exporte ITERACOES (valor congelado no piloto)}"
OUT="${OUT:-resultados/bruto}"
PLANO="${PLANO:-C1:1 C2:1 C2:2 C1:2 C1:3 C2:3}"   # ordem alternada/contrabalanceada
MOUNT_OPT="${MOUNT_OPT:-ro}"                       # no Fedora com SELinux: export MOUNT_OPT=ro,Z
mkdir -p "$OUT"
cpus_de() { case "$1" in C1) echo 0.5 ;; C2) echo 1.0 ;; *) echo 1.0 ;; esac; }

REF=$(python3 app/carga_cpu.py --n "$ITERACOES" --so-checksum) || exit 1
echo "N=$ITERACOES checksum_ref=$REF imagem=$IMAGEM_LAB" > "$OUT/referencia.txt"
[ -f "$OUT/status_execucoes.csv" ] || echo "arquivo,cond,rep,rc,wall_host_s,loadavg_antes" > "$OUT/status_execucoes.csv"

for item in $PLANO; do
  cond=${item%%:*}; rep=${item##*:}
  id="${cond}_r${rep}_$(date +%H%M%S)"; nome="so_a3_${id}"
  load=$(cut -d' ' -f1 /proc/loadavg)
  t0=$(date +%s.%N)
  timeout 90 docker run --rm --name "$nome" --network none \
    --cpus "$(cpus_de "$cond")" --memory 256m --memory-swap 256m --pids-limit 64 \
    --read-only --tmpfs /tmp --user 65534:65534 --cap-drop ALL --security-opt no-new-privileges \
    -e PYTHONDONTWRITEBYTECODE=1 \
    -v "$PWD/app:/app:${MOUNT_OPT}" \
    "$IMAGEM_LAB" python /app/carga_cpu.py --n "$ITERACOES" --esperado "$REF" --cond "$cond" --rep "$rep" \
    > "$OUT/$id.json" 2> "$OUT/$id.err"
  rc=$?
  t1=$(date +%s.%N)
  [ "$rc" -eq 124 ] && docker rm -f "$nome" > /dev/null 2>&1
  wall=$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.3f", b-a}')
  echo "$id.json,$cond,$rep,$rc,$wall,$load" >> "$OUT/status_execucoes.csv"
  echo "[$id] rc=$rc wall_host=${wall}s"
  sleep 5
done
