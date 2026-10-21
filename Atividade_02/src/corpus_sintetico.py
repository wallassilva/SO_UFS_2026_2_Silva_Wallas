#!/usr/bin/env python3
"""Gerador de corpus sintético para o GenResearch-Servidor.

Os documentos são feitos de pseudo-palavras (sílabas aleatórias) organizadas em
20 "temas". Cada documento tem um tema dominante; consultas são montadas com
palavras de um tema, então a recuperação por similaridade encontra trechos
coerentes. Tudo é determinístico (semente fixa) e 100% sintético: não há dados
pessoais, sigilosos ou protegidos por direitos autorais.

Uso:
    python src/corpus_sintetico.py --docs 500 --palavras 1000 --saida dados/corpus_pequeno
"""
import argparse
import random
from pathlib import Path

TEMAS = ["memoria", "paginacao", "swap", "cache", "fila", "mutex", "deadlock",
         "disco", "arquivo", "processo", "thread", "escalonamento",
         "interrupcao", "kernel", "vetor", "embedding", "indice", "modelo",
         "token", "contexto"]

SILABAS = ("ba be bi bo bu ca ce ci co cu da de di do du fa fe fi fo fu "
           "ga ge gi go gu la le li lo lu ma me mi mo mu na ne ni no nu "
           "pa pe pi po pu ra re ri ro ru sa se si so su ta te ti to tu "
           "va ve vi vo vu").split()


def gerar_vocabulario(seed=42, n_geral=1500, n_por_tema=120):
    """Retorna (lista de palavras gerais, dict tema -> palavras do tema)."""
    rng = random.Random(seed)
    vistos = set()

    def nova(prefixo=""):
        while True:
            n = rng.choice([2, 3, 3, 4])
            p = prefixo + "".join(rng.choice(SILABAS) for _ in range(n))
            if p not in vistos:
                vistos.add(p)
                return p

    geral = [nova() for _ in range(n_geral)]
    temas = {t: [nova(t[:3]) for _ in range(n_por_tema)] for t in TEMAS}
    return geral, temas


def gerar_corpus(destino, n_docs, palavras_por_doc, seed=42, frac_tema=0.6):
    """Cria n_docs arquivos .txt em `destino`. Retorna (n_docs, bytes_total)."""
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    geral, temas = gerar_vocabulario()
    rng = random.Random(seed + 1)
    lista_temas = list(temas)
    total = 0
    k_tema = int(palavras_por_doc * frac_tema)
    k_geral = palavras_por_doc - k_tema
    for i in range(n_docs):
        tema = lista_temas[i % len(lista_temas)]
        mix = rng.choices(temas[tema], k=k_tema) + rng.choices(geral, k=k_geral)
        rng.shuffle(mix)
        texto = "\n".join(" ".join(mix[j:j + 20]) for j in range(0, len(mix), 20))
        dados = texto.encode("utf-8")
        (destino / f"doc_{i:06d}.txt").write_bytes(dados)
        total += len(dados)
    return n_docs, total


def gerar_consultas(n, seed=7, palavras=5):
    """n consultas distintas (palavras de um mesmo tema)."""
    _, temas = gerar_vocabulario()
    rng = random.Random(seed)
    nomes = list(temas)
    vistas, saida = set(), []
    while len(saida) < n:
        t = rng.choice(nomes)
        q = " ".join(rng.sample(temas[t], palavras))
        if q not in vistas:
            vistas.add(q)
            saida.append(q)
    return saida


def montar_carga(n_req, n_unicas, seed=7, carga="repetidas"):
    """Lista de n_req consultas.

    repetidas: sorteia de um conjunto de n_unicas consultas (distribuição
               enviesada: poucas consultas muito frequentes) -> cache ajuda.
    distintas: todas diferentes entre si -> cache não ajuda.
    """
    if carga == "distintas":
        return gerar_consultas(n_req, seed=seed + 100)
    pool = gerar_consultas(n_unicas, seed=seed)
    pesos = [1.0 / ((i + 1) ** 0.8) for i in range(len(pool))]
    return random.Random(seed + 1).choices(pool, weights=pesos, k=n_req)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--docs", type=int, default=500)
    ap.add_argument("--palavras", type=int, default=1000)
    ap.add_argument("--saida", default="dados/corpus_pequeno")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    n, b = gerar_corpus(a.saida, a.docs, a.palavras, a.seed)
    print(f"{n} documentos, {b/1e6:.1f} MB em {a.saida}")
