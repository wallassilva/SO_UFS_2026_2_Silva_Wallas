#!/usr/bin/env python3
"""Resumo (média ± desvio entre repetições) dos CSVs. Saída: terminal + resultados/resumo.md"""
import csv, statistics as st
from collections import defaultdict
from pathlib import Path

RES = Path(__file__).resolve().parent.parent / "resultados"
saida = []

def ler(nome):
    p = RES / nome
    return list(csv.DictReader(open(p))) if p.exists() else []

def tabela(titulo, arquivo, chave, cols, txt=()):
    linhas = ler(arquivo)
    saida.append(f"\n### {titulo}  ({arquivo}, {len(linhas)} linhas)\n")
    if not linhas:
        saida.append("(arquivo ausente)")
        return
    g = defaultdict(list)
    for l in linhas:
        g[chave(l)].append(l)
    saida.append("| configuração | n | " + " | ".join(list(txt) + cols) + " |")
    saida.append("|" + "---|" * (len(cols) + len(txt) + 2))
    for k in sorted(g):
        ls = g[k]
        celulas = [" / ".join(sorted({l.get(t, "") for l in ls})) for t in txt]
        for c in cols:
            v = [float(l[c]) for l in ls if l.get(c) not in (None, "")]
            celulas.append(f"{st.mean(v):.2f}±{st.pstdev(v):.2f}" if v else "-")
        saida.append(f"| {k} | {len(ls)} | " + " | ".join(celulas) + " |")

tabela("Ingestão", "ingestao.csv", lambda l: l["corpus_nome"] if "corpus_nome" in l else l["indice"],
       ["n_docs", "n_chunks", "bytes_corpus", "bytes_indice", "t_embeddings_s", "t_total_s"])
tabela("mmap vs read", "mmap_vs_read.csv",
       lambda l: f"{float(l['tamanho_mb']):.0f}MB {l['padrao']} {l['cache']} {l['metodo']}",
       ["t_leitura_ms", "rss_delta_mb", "faltas_menores", "faltas_maiores", "io_disco_mb"])
tabela("C1/C2 (no app)", "c1c2.csv", lambda l: l["rotulo"],
       ["t_carga_indice_s", "vazao_req_s", "lat_p95_ms", "rss_pico_mb", "faltas_maiores_exec", "io_read_mb"])
tabela("C3 concorrência", "c3.csv", lambda l: l["rotulo"],
       ["vazao_req_s", "lat_mediana_ms", "lat_p95_ms", "espera_fila_media_ms", "fila_media", "fila_max", "utilizacao_workers"])
tabela("C4 cache", "c4.csv", lambda l: l["rotulo"],
       ["cache_taxa_acerto", "cache_evicoes", "cache_tempo_economizado_s", "vazao_req_s", "lat_p95_ms"])
tabela("C5 pressão de memória", "c5.csv", lambda l: l["rotulo"],
       ["rss_pico_mb", "vsz_pico_mb", "memavail_min_mb", "swap_usado_max_mb", "faltas_maiores_exec", "lat_p95_ms"])
tabela("C6 falhas", "c6.csv", lambda l: l["rotulo"],
       ["n_enviadas", "n_processadas", "n_rejeitadas", "n_retentativas_fila", "n_falhas", "perdidos"], txt=["status"])
tabela("Sincronização: cache", "sincronizacao.csv",
       lambda l: l["variante"] if l["demo"] == "cache_compartilhado" else "~",
       ["tempo_s", "atualizacoes_perdidas", "computacoes_redundantes"])
tabela("Sincronização: log e buffer", "sincronizacao.csv",
       lambda l: f"{l['demo']}/{l['variante']}" if l["demo"] in ("log_concorrente", "buffer_limitado") else "~",
       ["linhas_corrompidas", "itens_perdidos", "itens_duplicados"])
tabela("Sincronização: deadlock", "sincronizacao.csv",
       lambda l: f"{l['demo']}/{l['variante']}" if l["demo"] == "deadlock" else "~",
       ["tempo_s", "deadlocks_detectados"], txt=["deadlock_confirmado"])
texto = "\n".join(saida)
print(texto)
(RES / "resumo.md").write_text(texto)