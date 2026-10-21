#!/usr/bin/env python3
"""Orquestrador dos experimentos comparativos (Parte C).

Cada execução roda `genresearch.py executar` em um PROCESSO NOVO (métricas de memória
limpas) e o resultado bruto vai para resultados/brutos/<id>.json + <id>.log.
Cada grupo gera resultados/<grupo>.csv com TODAS as repetições.

    python src/experimentos.py preparar            # gera corpora e índices (uma vez)
    python src/experimentos.py c1c2                # leitura convencional x mmap (no app)
    python src/experimentos.py c3                  # concorrência e fila (1, 2, 4 workers)
    python src/experimentos.py c4                  # cache compartilhado
    python src/experimentos.py c5                  # pressão de memória
    python src/experimentos.py c6                  # falhas controladas
    python src/experimentos.py ollama --modelo phi4-mini   # demonstração com LLM real
    python src/experimentos.py tudo                # preparar + c1c2..c6
Opções globais: --reps N (padrão 3)  --rapido (menos requisições, sem corpus grande)
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SRC = RAIZ / "src"
BRUTOS = RAIZ / "resultados" / "brutos"
DADOS = RAIZ / "dados"

# (n_docs, palavras_por_doc) -> trechos = n_docs * palavras / 100
CORPORA = {"pequeno": (500, 1000),     # ~5 mil trechos
           "medio": (2000, 2500),      # ~50 mil trechos
           "grande": (8000, 5000)}     # ~400 mil trechos (~410 MB de vetores)


def indice(nome):
    return str((DADOS / f"indice_{nome}").relative_to(RAIZ))


def salvar_csv(linhas, caminho):
    campos = []
    for l in linhas:
        for k in l:
            if k not in campos:
                campos.append(k)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas)


def rodar(grupo, rotulo, cfg, rep):
    cfg = dict(cfg)
    cfg["id"] = f"{grupo}_{rotulo}_r{rep}"
    cfg["saida"] = str(BRUTOS.relative_to(RAIZ))
    env = dict(os.environ, MALLOC_ARENA_MAX="2")
    cmd = [sys.executable, str(SRC / "genresearch.py"), "executar", "--config-json", json.dumps(cfg)]
    r = subprocess.run(cmd, cwd=RAIZ, env=env, capture_output=True, text=True, timeout=3600)
    if r.returncode != 0:
        print(r.stdout, r.stderr)
        raise SystemExit(f"falha na execução {cfg['id']}")
    print("  " + r.stdout.strip().splitlines()[-1], flush=True)
    dados = json.loads((BRUTOS / f"{cfg['id']}.json").read_text())
    dados.update({"grupo": grupo, "rotulo": rotulo, "rep": rep})
    time.sleep(0.5)
    return dados


def executar_grupo(grupo, configs, reps):
    linhas = []
    for rotulo, cfg in configs:
        for rep in range(1, reps + 1):
            print(f"[{grupo}] {rotulo} (rep {rep}/{reps})", flush=True)
            linhas.append(rodar(grupo, rotulo, cfg, rep))
    salvar_csv(linhas, RAIZ / "resultados" / f"{grupo}.csv")
    print(f"=> resultados/{grupo}.csv ({len(linhas)} execuções)\n")


# ------------------------------------------------------------------ preparar
def preparar(args):
    linhas = []
    for nome, (docs, palavras) in CORPORA.items():
        if args.rapido and nome == "grande":
            continue
        corpus = DADOS / f"corpus_{nome}"
        idx = DADOS / f"indice_{nome}"
        if not (idx / "meta.json").exists():
            print(f"[preparar] gerando corpus {nome}: {docs} docs x {palavras} palavras", flush=True)
            subprocess.run([sys.executable, str(SRC / "corpus_sintetico.py"), "--docs", str(docs),
                            "--palavras", str(palavras), "--saida", str(corpus)], check=True)
            subprocess.run([sys.executable, str(SRC / "genresearch.py"), "ingerir", "--corpus", str(corpus),
                            "--indice", str(idx), "--log", str(RAIZ / "resultados" / "logs" / f"ingestao_{nome}.log")],
                           check=True, capture_output=True, cwd=RAIZ)
        info = json.loads((idx / "ingestao.json").read_text())
        info["corpus_nome"] = nome
        linhas.append(info)
        print(f"  {nome}: {info['n_chunks']} trechos, índice {info['bytes_indice']/1e6:.1f} MB, "
              f"ingestão {info['t_total_s']} s")
    salvar_csv(linhas, RAIZ / "resultados" / "ingestao.csv")


# --------------------------------------------------------------- experimentos
def n_req(args, normal):
    return max(40, normal // 3) if args.rapido else normal


def c1c2(args):
    corpora = ["medio"] if args.rapido else ["medio", "grande"]
    configs = []
    for c in corpora:
        for mm in (False, True):
            for frio in (True, False):
                rot = f"{'C2_mmap' if mm else 'C1_read'}_{c}_{'frio' if frio else 'quente'}"
                configs.append((rot, dict(indice=indice(c), usar_mmap=mm, frio=frio, workers=2,
                                          carga="distintas", cache_capacidade=0, top_k=5,
                                          n_req=n_req(args, 300), ger_base_ms=5.0)))
    executar_grupo("c1c2", configs, args.reps)


def c3(args):
    configs = []
    for modo in ("simulado", "cpu"):
        for w in (1, 2, 4):
            configs.append((f"{modo}_w{w}_fila16", dict(indice=indice("medio"), workers=w, produtores=2,
                            fila_capacidade=16, gerador=modo, ger_base_ms=40.0, carga="distintas",
                            cache_capacidade=0, n_req=n_req(args, 240))))
    for fila in (2, 64):
        configs.append((f"simulado_w4_fila{fila}", dict(indice=indice("medio"), workers=4, produtores=2,
                        fila_capacidade=fila, gerador="simulado", ger_base_ms=40.0, carga="distintas",
                        cache_capacidade=0, n_req=n_req(args, 240))))
    executar_grupo("c3", configs, args.reps)


def c4(args):
    base = dict(indice=indice("medio"), workers=4, produtores=2, gerador="simulado", ger_base_ms=30.0,
                n_req=n_req(args, 400), n_unicas=100)
    configs = [
        ("sem_cache_repetidas", dict(base, carga="repetidas", cache_capacidade=0)),
        ("cache200_lru_repetidas", dict(base, carga="repetidas", cache_capacidade=200, cache_politica="lru")),
        ("cache20_lru_repetidas", dict(base, carga="repetidas", cache_capacidade=20, cache_politica="lru")),
        ("cache20_fifo_repetidas", dict(base, carga="repetidas", cache_capacidade=20, cache_politica="fifo")),
        ("cache200_lru_distintas", dict(base, carga="distintas", cache_capacidade=200, cache_politica="lru")),
    ]
    executar_grupo("c4", configs, args.reps)


def c5(args):
    corpora = ["pequeno", "medio"] if args.rapido else ["pequeno", "medio", "grande"]
    contextos = {"leve": dict(top_k=5, max_chars=1000), "pesado": dict(top_k=50, max_chars=12000)}
    configs = []
    for c in corpora:
        for mm in (False, True):
            for nome, ctx in contextos.items():
                configs.append((f"{c}_{'mmap' if mm else 'read'}_ctx{nome}",
                                dict(indice=indice(c), usar_mmap=mm, workers=4, carga="distintas",
                                     cache_capacidade=0, n_req=n_req(args, 150), **ctx)))
    executar_grupo("c5", configs, args.reps)


def c6(args):
    pequeno = indice("pequeno")
    grande = indice("medio" if args.rapido else "grande")
    base = dict(indice=pequeno, workers=2, n_req=n_req(args, 120), ger_base_ms=20.0)
    configs = [
        ("arquivo_ausente_sem_fallback", dict(base, indice="dados/indice_inexistente")),
        ("arquivo_ausente_com_fallback", dict(base, indice="dados/indice_inexistente", indice_fallback=pequeno)),
        ("fila_saturada", dict(base, workers=1, produtores=4, fila_capacidade=2, put_timeout=0.05,
                               put_retentativas=2, ger_base_ms=100.0, carga="distintas", cache_capacidade=0)),
        ("servico_falha_sem_retentativa", dict(base, taxa_falha=0.4, retentativas=0, carga="distintas",
                                               cache_capacidade=0)),
        ("servico_falha_com_retentativa", dict(base, taxa_falha=0.4, retentativas=3, carga="distintas",
                                               cache_capacidade=0)),
        ("ollama_indisponivel", dict(base, gerador="ollama", ollama_url="http://127.0.0.1:9", retentativas=1,
                                     timeout_ger=3.0, n_req=20, carga="distintas", cache_capacidade=0)),
    ]
    if args.limite_memoria:   # EXPERIMENTAL: RLIMIT_AS pode derrubar bibliotecas nativas (OpenBLAS)
        configs.append(("limite_memoria_com_fallback", dict(base, indice=grande, indice_fallback=pequeno,
                        limite_mem_extra_mb=30 if args.rapido else 120, usar_mmap=False)))
    executar_grupo("c6", configs, args.reps)


def ollama(args):
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3) as r:
            modelos = [m["name"] for m in json.load(r).get("models", [])]
    except Exception as e:
        raise SystemExit(f"Ollama não respondeu em localhost:11434 ({e}). Rode 'ollama serve'.")
    if not any(m.startswith(args.modelo) for m in modelos):
        raise SystemExit(f"Modelo '{args.modelo}' não encontrado. Disponíveis: {modelos}. "
                         "Use --modelo <nome exibido por 'ollama list'>.")
    configs = []
    for w in (1, 2):
        configs.append((f"ollama_w{w}", dict(indice=indice("pequeno"), workers=w, produtores=1, fila_capacidade=8,
                                             gerador="ollama", modelo=args.modelo, num_predict=24,
                                             max_chars=600, top_k=3, carga="distintas",
                                             cache_capacidade=0, n_req=args.n_ollama, retentativas=1)))
    executar_grupo("ollama", configs, args.reps)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("grupo", choices=["preparar", "c1c2", "c3", "c4", "c5", "c6", "ollama", "tudo"])
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--rapido", action="store_true")
    ap.add_argument("--modelo", default="phi4-mini")
    ap.add_argument("--limite-memoria", action="store_true", help="inclui o cenário experimental de limite de memória no c6")
    ap.add_argument("--n-ollama", type=int, default=8, help="requisições por execução no teste com LLM real")
    args = ap.parse_args()
    ordem = {"preparar": preparar, "c1c2": c1c2, "c3": c3, "c4": c4, "c5": c5, "c6": c6, "ollama": ollama}
    if args.grupo == "tudo":
        for g in ("preparar", "c1c2", "c3", "c4", "c5", "c6"):
            ordem[g](args)
    else:
        ordem[args.grupo](args)


if __name__ == "__main__":
    main()
