#!/usr/bin/env python3
"""Parte E (e C1/C2): leitura convencional (open/read/pread) x mapeamento (mmap).

Cada medição roda em um PROCESSO NOVO (modo --trial), para que RSS, VSZ e faltas de
página não se misturem entre medições. O orquestrador varia:
  * tamanho do arquivo (pequeno ... grande)
  * método: read | mmap
  * padrão: sequencial (arquivo inteiro, blocos de 1 MiB) | aleatório (leituras de 4 KiB)
  * cache: frio (páginas do arquivo removidas do cache de páginas) | quente (já em cache)
e repete cada combinação `--reps` vezes.

Uso:
    python src/mmap_vs_read.py                       # tamanhos 16, 256 e 1024 MB, 3 repetições
    python src/mmap_vs_read.py --tamanhos 16 128 --reps 3
    python src/mmap_vs_read.py --arquivos dados/indice_grande/vetores.npy   # arquivo real
Opcional (cache realmente frio, exige sudo):  --drop-caches
"""
import argparse
import csv
import json
import mmap
import os
import random
import resource
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BLOCO = 1 << 20
PAGINA = 4096


def _proc_status():
    d = {}
    with open("/proc/self/status") as f:
        for l in f:
            if l.startswith(("VmRSS", "VmSize", "RssFile", "VmHWM")):
                k, v = l.split(":")
                d[k] = int(v.split()[0])
    return d


def _proc_io():
    d = {}
    with open("/proc/self/io") as f:
        for l in f:
            k, v = l.split(":")
            d[k] = int(v)
    return d


def _fadvise_dontneed(caminho):
    fd = os.open(caminho, os.O_RDONLY)
    try:
        os.fsync(fd)
    except OSError:
        pass
    os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
    os.close(fd)


def _aquecer(caminho):
    """Lê o arquivo inteiro com read() para colocá-lo no cache de páginas."""
    with open(caminho, "rb", buffering=0) as f:
        while f.read(BLOCO):
            pass


def trial(caminho, metodo, padrao, frio, n_acessos, semente):
    if frio:
        _fadvise_dontneed(caminho)
    else:
        _aquecer(caminho)
    tam = os.path.getsize(caminho)
    rnd = random.Random(semente)
    offs = [rnd.randrange(0, max(1, tam - PAGINA)) for _ in range(n_acessos)]

    st0, io0, ru0 = _proc_status(), _proc_io(), resource.getrusage(resource.RUSAGE_SELF)
    t0 = time.perf_counter()
    soma = 0
    if metodo == "read":
        f = open(caminho, "rb", buffering=0)
        fd = f.fileno()
        t_abertura = time.perf_counter() - t0
        t1 = time.perf_counter()
        if padrao == "sequencial":
            while True:
                b = f.read(BLOCO)
                if not b:
                    break
                soma += b.count(b"\n")
        else:
            for o in offs:
                soma += len(os.pread(fd, PAGINA, o))
    else:
        f = open(caminho, "rb")
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        t_abertura = time.perf_counter() - t0
        t1 = time.perf_counter()
        if padrao == "sequencial":
            for o in range(0, tam, BLOCO):
                soma += mm[o:o + BLOCO].count(b"\n")
        else:
            for o in offs:
                soma += len(mm[o:o + PAGINA])
    t_leitura = time.perf_counter() - t1
    st1, io1, ru1 = _proc_status(), _proc_io(), resource.getrusage(resource.RUSAGE_SELF)
    if metodo == "mmap":
        mm.close()
    f.close()
    return {
        "t_abertura_ms": round(t_abertura * 1000, 3), "t_leitura_ms": round(t_leitura * 1000, 2),
        "rss_delta_mb": round((st1["VmRSS"] - st0["VmRSS"]) / 1024, 2),
        "rss_file_delta_mb": round((st1["RssFile"] - st0["RssFile"]) / 1024, 2),
        "vsz_delta_mb": round((st1["VmSize"] - st0["VmSize"]) / 1024, 2),
        "rss_pico_mb": round(st1["VmHWM"] / 1024, 2),
        "faltas_menores": ru1.ru_minflt - ru0.ru_minflt,
        "faltas_maiores": ru1.ru_majflt - ru0.ru_majflt,
        "io_disco_mb": round((io1["read_bytes"] - io0["read_bytes"]) / 1e6, 2),
        "io_rchar_mb": round((io1["rchar"] - io0["rchar"]) / 1e6, 2),
        "syscalls_leitura": io1["syscr"] - io0["syscr"],
        "checksum": soma,
    }


def criar_arquivo(caminho, mb):
    caminho = Path(caminho)
    if caminho.exists() and caminho.stat().st_size == mb * (1 << 20):
        return
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "wb") as f:
        for _ in range(mb):
            f.write(os.urandom(1 << 20))
        f.flush()
        os.fsync(f.fileno())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trial", action="store_true", help="(interno) uma medição")
    ap.add_argument("--caminho")
    ap.add_argument("--metodo", choices=["read", "mmap"])
    ap.add_argument("--padrao", choices=["sequencial", "aleatorio"])
    ap.add_argument("--frio", type=int, default=1)
    ap.add_argument("--tamanhos", type=int, nargs="+", default=[16, 256, 1024], help="MB")
    ap.add_argument("--arquivos", nargs="*", default=[], help="usar arquivos existentes")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--acessos", type=int, default=20000)
    ap.add_argument("--saida", default="resultados/mmap_vs_read.csv")
    ap.add_argument("--drop-caches", action="store_true", help="usa sudo para drop_caches antes de cada medição fria")
    a = ap.parse_args()

    if a.trial:
        print(json.dumps(trial(a.caminho, a.metodo, a.padrao, bool(a.frio), a.acessos, 1234)))
        return

    alvos = [(Path(p), "real") for p in a.arquivos]
    for mb in a.tamanhos:
        p = RAIZ / "dados" / "mmap" / f"arquivo_{mb}mb.bin"
        criar_arquivo(p, mb)
        alvos.append((p, f"{mb}MB"))

    linhas = []
    total = len(alvos) * 2 * 2 * 2 * a.reps
    n = 0
    for caminho, rotulo in alvos:
        tam_mb = round(caminho.stat().st_size / (1 << 20), 1)
        for padrao in ("sequencial", "aleatorio"):
            for metodo in ("read", "mmap"):
                for frio in (1, 0):
                    for rep in range(1, a.reps + 1):
                        n += 1
                        if frio and a.drop_caches:
                            subprocess.run("sync; echo 3 | sudo tee /proc/sys/vm/drop_caches >/dev/null",
                                           shell=True, check=False)
                        cmd = [sys.executable, __file__, "--trial", "--caminho", str(caminho),
                               "--metodo", metodo, "--padrao", padrao, "--frio", str(frio),
                               "--acessos", str(a.acessos)]
                        r = subprocess.run(cmd, capture_output=True, text=True)
                        if r.returncode != 0:
                            print(r.stderr)
                            raise SystemExit("falha em uma medição")
                        dados = json.loads(r.stdout.strip().splitlines()[-1])
                        linha = {"arquivo": caminho.name, "tamanho_mb": tam_mb, "metodo": metodo,
                                 "padrao": padrao, "cache": "frio" if frio else "quente", "rep": rep,
                                 "horario": time.strftime("%Y-%m-%dT%H:%M:%S"), **dados}
                        linhas.append(linha)
                        print(f"[{n}/{total}] {caminho.name} {metodo:4s} {padrao:10s} "
                              f"{linha['cache']:6s} rep{rep}: leitura={dados['t_leitura_ms']:9.1f} ms "
                              f"faltas(min/maj)={dados['faltas_menores']}/{dados['faltas_maiores']} "
                              f"rss+{dados['rss_delta_mb']} MB")
    saida = RAIZ / a.saida
    saida.parent.mkdir(parents=True, exist_ok=True)
    with open(saida, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    print(f"\nResultados brutos: {saida}")


if __name__ == "__main__":
    main()
