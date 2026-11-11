#!/usr/bin/env python3
"""Carga deterministica de CPU com trabalho fixo (LCG + XOR). Saida: 1 linha JSON."""
import argparse, json, resource, sys, time
from pathlib import Path

CG = Path("/sys/fs/cgroup")  # dentro do conteiner (cgroup v2 + cgroupns privado) = cgroup do proprio conteiner


def ler(nome):
    try:
        return (CG / nome).read_text().strip()
    except OSError:
        return None


def ler_stat(nome):
    d = {}
    for linha in (ler(nome) or "").splitlines():
        k, _, v = linha.partition(" ")
        if v.strip().isdigit():
            d[k] = int(v)
    return d


def trabalho(n, limite_s):
    x, acc, feito = 123456789, 0, 0
    t0 = time.monotonic()
    while feito < n:
        bloco = min(1_000_000, n - feito)
        for _ in range(bloco):
            x = (x * 1103515245 + 12345) & 0x7FFFFFFF
            acc ^= x
        feito += bloco
        if time.monotonic() - t0 > limite_s:
            return feito, acc, "TIMEOUT_INTERNO"
    return feito, acc, "OK"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--esperado", type=int, default=None)
    ap.add_argument("--cond", default="")
    ap.add_argument("--rep", default="")
    ap.add_argument("--limite", type=float, default=60.0)
    ap.add_argument("--so-checksum", action="store_true", help="imprime so o checksum (referencia no host)")
    a = ap.parse_args()
    if a.so_checksum:
        print(trabalho(a.n, 1e9)[1])
        return 0

    antes = ler_stat("cpu.stat")
    cpu0, t0 = time.process_time(), time.monotonic()
    feito, chk, status = trabalho(a.n, a.limite)
    wall, cpu = time.monotonic() - t0, time.process_time() - cpu0
    depois = ler_stat("cpu.stat")

    def delta(k):
        return depois[k] - antes.get(k, 0) if k in depois else None

    correto = (status == "OK" and a.esperado is not None and chk == a.esperado)
    print(json.dumps({
        "cond": a.cond, "rep": a.rep, "python": sys.version.split()[0],
        "n_pedido": a.n, "n_feito": feito, "checksum": chk, "esperado": a.esperado,
        "correto": correto, "status": status,
        "wall_s": round(wall, 4), "cpu_proc_s": round(cpu, 4),
        "trab_por_s": round(feito / wall, 1) if wall > 0 else None,
        "cpu_max": ler("cpu.max"), "memory_max": ler("memory.max"),
        "memory_swap_max": ler("memory.swap.max"), "pids_max": ler("pids.max"),
        "memory_current": ler("memory.current"), "memory_peak": ler("memory.peak"),
        "rss_pico_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "cpu_stat_delta": {k: delta(k) for k in ("usage_usec", "nr_periods", "nr_throttled", "throttled_usec")},
    }))
    return 0 if correto else 2


if __name__ == "__main__":
    sys.exit(main())
