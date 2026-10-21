#!/usr/bin/env python3
"""Gera os gráficos (PNG) a partir dos CSVs em resultados/. Gráficos cujo CSV não
existe são pulados. Barras de erro = desvio padrão entre as repetições.

    python src/graficos.py
"""
import csv
import statistics as st
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
RES = RAIZ / "resultados"
OUT = RES / "graficos"


def ler(nome):
    p = RES / nome
    if not p.exists():
        print(f"(pulando {nome}: não existe)")
        return None
    with open(p) as f:
        return list(csv.DictReader(f))


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def agrupar(linhas, chave, campo):
    g = defaultdict(list)
    for l in linhas:
        g[chave(l)].append(num(l[campo]))
    return {k: (st.mean(v), st.pstdev(v) if len(v) > 1 else 0.0) for k, v in g.items()}


def barras(dados, titulo, ylabel, arq, rot=30):
    ks = list(dados)
    fig, ax = plt.subplots(figsize=(max(6, 0.9 * len(ks)), 4))
    ax.bar(range(len(ks)), [dados[k][0] for k in ks], yerr=[dados[k][1] for k in ks], capsize=3)
    ax.set_xticks(range(len(ks)))
    ax.set_xticklabels(ks, rotation=rot, ha="right", fontsize=8)
    ax.set_title(titulo)
    ax.set_ylabel(ylabel)
    fig.tight_layout()
    fig.savefig(OUT / arq, dpi=150)
    plt.close(fig)
    print("gerado", OUT / arq)


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    c3 = ler("c3.csv")
    if c3:
        fig, ax = plt.subplots(figsize=(6, 4))
        for modo in ("simulado", "cpu"):
            sel = [l for l in c3 if l["gerador"] == modo and l["fila_capacidade"] == "16"]
            g = agrupar(sel, lambda l: int(l["workers"]), "vazao_req_s")
            ks = sorted(g)
            ax.errorbar(ks, [g[k][0] for k in ks], yerr=[g[k][1] for k in ks], marker="o", label=f"geração {modo}")
        ax.set_xlabel("workers (threads)")
        ax.set_ylabel("vazão (req/s)")
        ax.set_xticks([1, 2, 4])
        ax.set_title("C3: vazão x workers (espera/E-S vs CPU, limite da GIL)")
        ax.legend()
        fig.tight_layout()
        fig.savefig(OUT / "c3_vazao_workers.png", dpi=150)
        plt.close(fig)
        barras(agrupar(c3, lambda l: l["rotulo"], "lat_p95_ms"), "C3: latência p95", "ms", "c3_latencia_p95.png")
        barras(agrupar(c3, lambda l: l["rotulo"], "fila_media"), "C3: tamanho médio da fila", "itens", "c3_fila_media.png")

    c4 = ler("c4.csv")
    if c4:
        barras(agrupar(c4, lambda l: l["rotulo"], "cache_taxa_acerto"), "C4: taxa de acerto do cache", "taxa", "c4_taxa_acerto.png")
        barras(agrupar(c4, lambda l: l["rotulo"], "vazao_req_s"), "C4: vazão", "req/s", "c4_vazao.png")
        barras(agrupar(c4, lambda l: l["rotulo"], "cache_tempo_economizado_s"), "C4: tempo economizado pelo cache", "s", "c4_tempo_economizado.png")

    c12 = ler("c1c2.csv")
    if c12:
        barras(agrupar(c12, lambda l: l["rotulo"], "t_carga_indice_s"), "C1 x C2: tempo de carga do índice", "s", "c1c2_carga_indice.png")
        barras(agrupar(c12, lambda l: l["rotulo"], "faltas_maiores_exec"), "C1 x C2: faltas de página maiores na execução", "faltas", "c1c2_faltas_maiores.png")
        barras(agrupar(c12, lambda l: l["rotulo"], "rss_pico_mb"), "C1 x C2: RSS de pico", "MB", "c1c2_rss.png")

    c5 = ler("c5.csv")
    if c5:
        barras(agrupar(c5, lambda l: l["rotulo"], "rss_pico_mb"), "C5: RSS de pico por corpus/modo/contexto", "MB", "c5_rss.png", 60)
        barras(agrupar(c5, lambda l: l["rotulo"], "lat_p95_ms"), "C5: latência p95", "ms", "c5_latencia.png", 60)
        barras(agrupar(c5, lambda l: l["rotulo"], "faltas_maiores_exec"), "C5: faltas maiores", "faltas", "c5_faltas.png", 60)
        barras(agrupar(c5, lambda l: l["rotulo"], "memavail_min_mb"), "C5: MemAvailable mínimo", "MB", "c5_memavailable.png", 60)

    mm = ler("mmap_vs_read.csv")
    if mm:
        fig, eixos = plt.subplots(2, 2, figsize=(10, 7))
        for i, padrao in enumerate(("sequencial", "aleatorio")):
            for j, cache in enumerate(("frio", "quente")):
                ax = eixos[i][j]
                sel = [l for l in mm if l["padrao"] == padrao and l["cache"] == cache]
                tams = sorted({num(l["tamanho_mb"]) for l in sel})
                for k, metodo in enumerate(("read", "mmap")):
                    g = agrupar([l for l in sel if l["metodo"] == metodo], lambda l: num(l["tamanho_mb"]), "t_leitura_ms")
                    ax.bar([x + 0.4 * k for x in range(len(tams))], [g.get(t, (0, 0))[0] for t in tams],
                           0.4, yerr=[g.get(t, (0, 0))[1] for t in tams], capsize=2, label=metodo)
                ax.set_xticks([x + 0.2 for x in range(len(tams))])
                ax.set_xticklabels([f"{t:.0f} MB" for t in tams])
                ax.set_yscale("log")
                ax.set_title(f"{padrao}, cache {cache}")
                ax.set_ylabel("tempo de leitura (ms, log)")
                ax.legend()
        fig.tight_layout()
        fig.savefig(OUT / "mmap_vs_read_tempo.png", dpi=150)
        plt.close(fig)
        print("gerado", OUT / "mmap_vs_read_tempo.png")
        seq = [l for l in mm if l["padrao"] == "sequencial" and l["cache"] == "frio"]
        barras(agrupar(seq, lambda l: f"{l['metodo']}-{num(l['tamanho_mb']):.0f}MB", "rss_delta_mb"),
               "RSS adicionado (leitura sequencial, cache frio)", "MB", "mmap_vs_read_rss.png")
        barras(agrupar(seq, lambda l: f"{l['metodo']}-{num(l['tamanho_mb']):.0f}MB", "faltas_menores"),
               "Faltas de página menores (sequencial, frio)", "faltas", "mmap_vs_read_faltas.png")

    sy = ler("sincronizacao.csv")
    if sy:
        c = [l for l in sy if l["demo"] == "cache_compartilhado"]
        barras(agrupar(c, lambda l: l["variante"], "atualizacoes_perdidas"), "Cache: atualizações perdidas", "contagens", "sync_cache_perdidas.png", 0)
        barras(agrupar(c, lambda l: l["variante"], "computacoes_redundantes"), "Cache: computações redundantes", "contagens", "sync_cache_redundantes.png", 0)
        barras(agrupar(c, lambda l: l["variante"], "tempo_s"), "Cache: tempo por variante de lock", "s", "sync_cache_tempo.png", 0)
        b = [l for l in sy if l["demo"] == "buffer_limitado" and l["variante"] in ("sem_mutex", "com_mutex")]
        barras(agrupar(b, lambda l: l["variante"], "itens_perdidos"), "Buffer limitado: itens perdidos", "itens", "sync_buffer_perdidos.png", 0)
        lg = [l for l in sy if l["demo"] == "log_concorrente"]
        barras(agrupar(lg, lambda l: l["variante"], "linhas_corrompidas"), "Log: linhas corrompidas", "linhas", "sync_log_corrompidas.png", 0)


if __name__ == "__main__":
    main()
