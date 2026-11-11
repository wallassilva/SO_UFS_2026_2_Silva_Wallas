#!/usr/bin/env python3
"""Grafico detalhado C1 x C2 a partir de resultados/bruto/consolidado.csv (somente execucoes validas)."""
import csv, statistics as st, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

D = Path(sys.argv[1] if len(sys.argv) > 1 else "resultados/bruto")
N = None
ref = D / "referencia.txt"
if ref.exists():
    for tok in ref.read_text().split():
        if tok.startswith("N="):
            N = int(tok[2:])

rows = []
for r in csv.DictReader(open(D / "consolidado.csv", newline="")):
    if r["valido"] != "True":
        continue
    rows.append({"cond": r["cond"], "rep": int(r["rep"]), "wall": float(r["wall_s"]), "cpu": float(r["cpu_proc_s"]),
                 "tps": float(r["trab_por_s"]) / 1e6, "thr": float(r["throttled_usec"] or 0) / 1e6,
                 "nthr": int(float(r["nr_throttled"] or 0))})
rows.sort(key=lambda r: (r["cond"], r["rep"]))
conds = sorted({r["cond"] for r in rows})
COR = {"C1": "#E8833A", "C2": "#3B7DD8"}
NOME = {"C1": "C1 (0,5 CPU)", "C2": "C2 (1,0 CPU)"}
med = lambda c, k: st.median([r[k] for r in rows if r["cond"] == c])
br = lambda x, d=2: f"{x:.{d}f}".replace(".", ",")

plt.rcParams.update({"font.size": 10.5, "axes.spines.top": False, "axes.spines.right": False})
fig, ax = plt.subplots(1, 3, figsize=(16.5, 5.8), dpi=130, gridspec_kw={"width_ratios": [1.25, 1, 1]})

# A: onde foi o tempo (CPU + throttling) por execucao
a = ax[0]
for i, r in enumerate(rows):
    a.bar(i, r["cpu"], color="#4C78A8", label="CPU do processo" if i == 0 else None)
    a.bar(i, r["thr"], bottom=r["cpu"], color="#E45756", label="Tempo em throttling" if i == 0 else None)
    a.plot(i, r["wall"], "kD", ms=6, label="Tempo de parede" if i == 0 else None, zorder=3)
a.set_xticks(range(len(rows)))
a.set_xticklabels([f'{r["cond"]}\nr{r["rep"]}' for r in rows])
a.set_ylabel("segundos")
a.set_title("A. Onde foi o tempo: CPU + throttling ≈ tempo de parede", loc="left", fontweight="bold", fontsize=11)
a.legend(frameon=False, loc="upper right", fontsize=9.5)
a.set_ylim(0, max(r["wall"] for r in rows) * 1.18)

# B: trabalho por segundo
b = ax[1]
for i, c in enumerate(conds):
    v = [r["tps"] for r in rows if r["cond"] == c]
    b.bar(i, st.median(v), color=COR[c], alpha=0.35, width=0.6)
    b.vlines(i, min(v), max(v), color="k", lw=2)
    b.scatter([i] * len(v), v, color="k", zorder=3, s=36)
    b.text(i, max(v) * 1.04, f"mediana {br(st.median(v))}", ha="center", fontsize=10, fontweight="bold")
b.set_xticks(range(len(conds))); b.set_xticklabels([f"{NOME[c]}\n(n={sum(r['cond'] == c for r in rows)})" for c in conds])
b.set_ylabel("milhões de iterações por segundo")
b.set_ylim(0, max(r["tps"] for r in rows) * 1.2)
if len(conds) == 2:
    ratio = st.median([r["tps"] for r in rows if r["cond"] == conds[1]]) / st.median([r["tps"] for r in rows if r["cond"] == conds[0]])
    b.text(0.5, 0.5 * max(r["tps"] for r in rows), f"razão {conds[1]}/{conds[0]}\n= {br(ratio)}×", ha="center", va="center",
           fontsize=13, fontweight="bold", color="#333333", bbox=dict(boxstyle="round", fc="white", ec="#999999"))
b.set_title("B. Trabalho concluído por segundo", loc="left", fontweight="bold", fontsize=11)

# C: CPU consumida para o mesmo trabalho
c_ = ax[2]
for i, c in enumerate(conds):
    v = [r["cpu"] for r in rows if r["cond"] == c]
    c_.scatter([i] * len(v), v, color=COR[c], s=70, edgecolor="k", zorder=3)
    c_.hlines(st.median(v), i - 0.3, i + 0.3, color="k", lw=2)
    c_.text(i + 0.34, st.median(v), f"{br(st.median(v))} s", va="center", fontsize=10, fontweight="bold")
c_.set_xticks(range(len(conds))); c_.set_xticklabels([NOME[c] for c in conds])
c_.set_xlim(-0.6, len(conds) - 0.4)
c_.set_ylabel("segundos de CPU do processo"); c_.set_ylim(0, max(r["cpu"] for r in rows) * 1.25)
if len(conds) == 2:
    d = 100 * (med(conds[0], "cpu") / med(conds[1], "cpu") - 1)
    c_.text(0.5, max(r["cpu"] for r in rows) * 1.12, f"{conds[0]} gastou +{br(d, 0)}% de CPU (mediana)\npara o mesmo trabalho; causa não determinada",
            ha="center", fontsize=9.5, color="#333333")
c_.set_title("C. CPU gasta no mesmo trabalho (linha = mediana)", loc="left", fontweight="bold", fontsize=11)

ntxt = f"N = {N:,} iterações fixas".replace(",", ".") if N else "trabalho fixo"
fig.suptitle("Quota de 0,5 CPU: processo limitado em quase todos os períodos de 100 ms (C1) × sem limitação efetiva (C2)",
             fontsize=14, fontweight="bold", y=0.995)
fig.text(0.5, 0.935, f"{ntxt} · 3 repetições por condição, em ordem alternada · carga de uma thread · pontos = execuções individuais",
         ha="center", fontsize=10, color="#555555")
fig.tight_layout(rect=(0, 0, 1, 0.90))
out = D / "grafico_c1_c2_detalhado.png"
fig.savefig(out, bbox_inches="tight", facecolor="white")
print("gerado:", out)
