#!/usr/bin/env bash
# Evidências de processos, threads, E/S, memória e chamadas de sistema durante uma execução.
cd "$(dirname "$0")/.." || exit 1
mkdir -p evidencias
ARGS="--indice dados/indice_medio --workers 4 --produtores 2 --n-req 400 --carga distintas --cache-capacidade 0 --ger-base-ms 40"
python3 src/genresearch.py executar --id evid --saida evidencias $ARGS > evidencias/execucao_stdout.txt &
PID=$!
sleep 1
{
  echo "### PID $PID"; echo "### threads (ps -L)"; ps -L -p $PID -o pid,tid,psr,pcpu,stat,comm
  echo "### /proc/$PID/status"; grep -E "Threads|VmRSS|VmSize|VmHWM|RssFile|RssAnon|voluntary" /proc/$PID/status
  echo "### top -H"; top -H -b -n1 -p $PID | head -20
  echo "### /proc/$PID/io"; cat /proc/$PID/io
  echo "### ollama (se existir)"; ps -eo pid,rss,vsz,comm | grep -i ollama
} > evidencias/processos_threads.txt 2>&1
vmstat 1 5 > evidencias/vmstat.txt
command -v iostat >/dev/null && iostat -xz 1 5 > evidencias/iostat.txt
wait $PID
if command -v strace >/dev/null; then
  strace -f -c -o evidencias/strace_resumo.txt python3 src/genresearch.py executar --id evid_strace --saida evidencias --usar-mmap --n-req 60 --indice dados/indice_medio --cache-capacidade 0 --carga distintas >/dev/null
  strace -f -e trace=openat,mmap,pread64,read,futex -o evidencias/strace_detalhe.txt -s 40 python3 src/mmap_vs_read.py --trial --caminho dados/mmap/arquivo_16mb.bin --metodo mmap --padrao sequencial --frio 1 --acessos 100 >/dev/null
fi
echo "evidências em evidencias/"
