#!/usr/bin/env bash
# Parte B (namespaces) + Parte D (mount read-only). Encerra so os conteineres que criou.
set -u
: "${IMAGEM_LAB:?exporte IMAGEM_LAB}"
MOUNT_OPT="${MOUNT_OPT:-ro}"            # Fedora/SELinux: export MOUNT_OPT=ro,Z
OUT=resultados/namespaces; mkdir -p "$OUT"
A=so_a3_nsA; B=so_a3_nsB
trap 'docker rm -f "$A" "$B" >/dev/null 2>&1' EXIT

for N in "$A" "$B"; do docker run -d --name "$N" --network none "$IMAGEM_LAB" sleep 120 >/dev/null; done

declare -A H
{
  echo "# coleta $(date -Is)"
  for N in "$A" "$B"; do
    echo "== $N"
    echo "PID_host=$(docker inspect --format '{{.State.Pid}}' "$N")"
    echo "PID1_comm=$(docker exec "$N" sh -c 'cat /proc/1/comm')"
    for ns in pid mnt net; do H[$N,$ns]=$(docker exec "$N" readlink /proc/1/ns/$ns); echo "$ns=${H[$N,$ns]}"; done
    echo "interfaces=$(docker exec "$N" sh -c 'tail -n +3 /proc/net/dev | cut -d: -f1 | tr -d " " | tr "\n" " "')"
  done
  echo "== comparacao (terminal do host = readlink /proc/self/ns/*; valido se o daemon e nativo)"
  printf '| recurso | A | B | terminal | A vs B |\n|---|---|---|---|---|\n'
  for ns in pid mnt net; do
    [ "${H[$A,$ns]}" = "${H[$B,$ns]}" ] && r=IGUAIS || r=DIFERENTES
    printf '| %s | %s | %s | %s | %s |\n' "$ns" "${H[$A,$ns]}" "${H[$B,$ns]}" "$(readlink /proc/self/ns/$ns)" "$r"
  done
} | tee "$OUT/namespaces.txt"

# ---------- Parte D: mount read-only ----------
mkdir -p dados_demo; printf '%s\n' 'Documento sintetico' > dados_demo/texto.txt
SEG=(--network none --cap-drop ALL --security-opt no-new-privileges --read-only --tmpfs /tmp)
{
  echo "# read-only $(date -Is)  (MOUNT_OPT=$MOUNT_OPT)"
  echo "## Teste 1: usuario 65534, /dados:${MOUNT_OPT}"
  docker run --rm --name so_a3_ro "${SEG[@]}" --user 65534:65534 -v "$PWD/dados_demo:/dados:${MOUNT_OPT}" "$IMAGEM_LAB" sh -c '
    id; echo "--- leitura"; cat /dados/texto.txt
    echo "--- escrita em /dados"; if touch /dados/novo.txt 2>&1; then echo "ESCRITA_PERMITIDA (inesperado)"; else echo "ESCRITA_NEGADA"; fi
    echo "--- controle: escrita em /tmp (tmpfs)"; touch /tmp/ok && echo "ESCRITA_TMP_OK"
    echo "--- controle: escrita em / (rootfs read-only)"; touch /raiz.txt 2>&1 || echo "ESCRITA_RAIZ_NEGADA"
    echo "--- mountinfo"; grep " /dados " /proc/self/mountinfo'
  echo "## Teste 2 (A/B): mesma identidade do dono ($(id -u):$(id -g)), rw vs ro"
  docker run --rm "${SEG[@]}" --user "$(id -u):$(id -g)" -v "$PWD/dados_demo:/dados:rw${MOUNT_OPT#ro}" "$IMAGEM_LAB" sh -c 'touch /dados/controle_rw.txt && echo "rw: escrita OK"'
  docker run --rm "${SEG[@]}" --user "$(id -u):$(id -g)" -v "$PWD/dados_demo:/dados:${MOUNT_OPT}" "$IMAGEM_LAB" sh -c 'touch /dados/controle_ro.txt 2>&1 || echo "ro: escrita negada"'
  rm -f dados_demo/controle_rw.txt
  echo "## No host, apos os testes:"; ls -l dados_demo
} 2>&1 | tee "$OUT/readonly.txt"
