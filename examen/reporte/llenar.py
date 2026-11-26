"""Llena el reporte del examen con los datos reales del clúster.

Lee lo que dejan barrido-cluster.sh, analyze.py, arranque.sh y evidencias.sh:
  resultados/tabla.csv, resultados/tiempos.csv            (kind, una laptop)
  examen/resultados/tabla.csv, tiempos-cluster.csv,
  examen/resultados/barrido/*.json, arranque.csv,
  examen/resultados/evidencias/04-drenado/drenado.txt     (k3s, 3 laptops)
y escribe examen/reporte/datos.tex: macros con cada número y las filas de las
tablas. Lo que todavía no existe sale en rojo como \\pend{...}.

Uso: python3 examen/reporte/llenar.py && (cd examen/reporte && latexmk -xelatex reporte.tex)
"""

import csv
import json
import re
import statistics as st
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
KIND = RAIZ / "resultados"
CLU = RAIZ / "examen" / "resultados"
SALIDA = Path(__file__).resolve().parent / "datos.tex"
FOTOS = 7390
ESTRATEGIAS = ("block", "lpt")


def leer(ruta: Path) -> list[dict]:
    if not ruta.exists():
        return []
    with open(ruta, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(x, fmt="{:.2f}"):
    return fmt.format(x) if x is not None else None


macros: dict[str, str | None] = {}


def m(nombre: str, valor) -> None:
    macros[nombre] = None if valor is None else str(valor)


# ---------------------------------------------------------------- tablas de analyze.py
tk = [r for r in leer(KIND / "tabla.csv") if r["estrategia"] in ESTRATEGIAS]
tc = [r for r in leer(CLU / "tabla.csv") if r["estrategia"] in ESTRATEGIAS]
idx = {(d, r["estrategia"], int(r["p"])): r for d, rs in (("k", tk), ("c", tc)) for r in rs}
ps = sorted({int(r["p"]) for r in tk + tc})


def celda(d, e, p, col, fmt="{:.2f}"):
    r = idx.get((d, e, p))
    if not r or r[col] == "":
        return "---"
    return fmt.format(float(r[col]))


def fps(d, e, p):
    r = idx.get((d, e, p))
    return f"{FOTOS / float(r['T_s']):.0f}" if r else "---"


filas = []
for e in ESTRATEGIAS:
    for p in ps:
        if (("k", e, p) not in idx) and (("c", e, p) not in idx):
            continue
        filas.append(f"{e} & {p} & {celda('k', e, p, 'T_s', '{:.1f}')} & {celda('c', e, p, 'T_s', '{:.1f}')}"
                     f" & {celda('k', e, p, 'S')} & {celda('c', e, p, 'S')}"
                     f" & {celda('k', e, p, 'E')} & {celda('c', e, p, 'E')}"
                     f" & {fps('k', e, p)} & {fps('c', e, p)}\\\\")
    filas.append("\\midrule")
if filas:
    filas.pop()
m("filasComparacion", "\n".join(filas) if tc else None)


def mejor(rs):
    """Fila con el mayor speedup."""
    return max(rs, key=lambda r: float(r["S"])) if rs else None


for d, rs, pre in (("k", tk, "Kind"), ("c", tc, "Clu")):
    b = mejor(rs)
    m(f"mejorS{pre}", num(float(b["S"])) if b else None)
    m(f"mejorP{pre}", b["p"] if b else None)
    m(f"mejorE{pre}", b["estrategia"] if b else None)
    rapido = min(rs, key=lambda r: float(r["T_s"])) if rs else None
    m(f"mejorT{pre}", num(float(rapido["T_s"]), "{:.1f}") if rapido else None)
    m(f"fps{pre}", f"{FOTOS / float(rapido['T_s']):.0f}" if rapido else None)
    m(f"fpsP{pre}", rapido["p"] if rapido else None)
    uno = [float(r["T_s"]) for r in rs if r["p"] == "1"]
    m(f"Tuno{pre}", num(st.mean(uno), "{:.1f}") if uno else None)
    m(f"pmax{pre}", max(int(r["p"]) for r in rs) if rs else None)
    fs = [float(r["f"]) for r in rs if r["f"] and int(r["p"]) <= 4]
    m(f"fSerial{pre}", num(st.mean(fs), "{:.3f}") if fs else None)

if tc and tk:
    rk = idx.get(("k", "lpt", 4)) or idx.get(("k", "block", 4))
    rc = idx.get(("c", "lpt", 4)) or idx.get(("c", "block", 4))
    m("Scuatro", f"{float(rk['S']):.2f} contra {float(rc['S']):.2f}" if rk and rc else None)
    m("vecesFps", num(float(macros["fpsClu"]) / float(macros["fpsKind"]), "{:.1f}"))
else:
    m("Scuatro", None)
    m("vecesFps", None)

# ---------------------------------------------------------------- ms por foto y arranque
def costo_por_p(tiempos: list[dict]) -> dict[int, tuple[float, float]]:
    """p -> (ms promedio por foto, fracción de T que no es cómputo)."""
    por_p = defaultdict(list)
    for r in tiempos:
        if r["estrategia"] not in ESTRATEGIAS:
            continue
        p, tareas, T = int(r["p"]), int(r["tareas"]), float(r["T_s"])
        computo = float(r["t_prom_s"]) * tareas
        por_p[p].append((computo / int(r["fotos"]) * 1000, 1 - computo / (p * T) if p == 1 else None))
    return {p: (st.mean(x for x, _ in v), st.mean(y for _, y in v) if v[0][1] is not None else None)
            for p, v in por_p.items()}


ck = costo_por_p(leer(KIND / "tiempos.csv"))
cc = costo_por_p(leer(CLU / "tiempos-cluster.csv"))
filas = []
for p in sorted(set(ck) | set(cc)):
    a = f"{ck[p][0]:.1f}" if p in ck else "---"
    b = f"{cc[p][0]:.1f}" if p in cc else "---"
    filas.append(f"{p} & {a} & {b}\\\\")
m("filasCosto", "\n".join(filas) if cc else None)
m("msUnoKind", num(ck[1][0], "{:.1f}") if 1 in ck else None)
m("msUnoClu", num(cc[1][0], "{:.1f}") if 1 in cc else None)
m("arranqueKind", num(ck[1][1] * 100, "{:.0f}") if 1 in ck else None)
m("arranqueClu", num(cc[1][1] * 100, "{:.0f}") if 1 in cc else None)
pk = max(ck) if ck else None
pc = max(cc) if cc else None
m("msMaxKind", num(ck[pk][0], "{:.1f}") if pk else None)
m("msMaxClu", num(cc[pc][0], "{:.1f}") if pc else None)

# ---------------------------------------------------------------- por nodo, con p = 1
por_nodo = defaultdict(lambda: [0.0, 0, 0])   # nodo -> [segundos, fotos, tareas]
por_nodo_max = defaultdict(lambda: [0.0, 0, 0])
for j in sorted((CLU / "barrido").glob("*.json")):
    mt = re.search(r"-p(\d+)-", j.name)
    if not mt:
        continue
    p = int(mt.group(1))
    s = json.loads(j.read_text(encoding="utf-8"))
    destino = por_nodo if p == 1 else por_nodo_max if p == pc else None
    if destino is None:
        continue
    for t in s["por_tarea"]:
        d = destino[t["nodo"]]
        d[0] += t["t_computo_s"]
        d[1] += t["fotos"]
        d[2] += 1
filas = []
for nodo in sorted(set(por_nodo) | set(por_nodo_max)):
    a, b = por_nodo.get(nodo), por_nodo_max.get(nodo)
    filas.append(f"\\texttt{{{nodo}}} & {a[0] / a[1] * 1000:.1f} & " if a and a[1] else f"\\texttt{{{nodo}}} & --- & ")
    filas[-1] += (f"{b[0] / b[1] * 1000:.1f} & {b[2]}\\\\" if b and b[1] else "--- & ---\\\\")
m("filasNodos", "\n".join(filas) if filas else None)

# ---------------------------------------------------------------- arranque en frío y caliente
arr = leer(CLU / "arranque.csv")
for caso, nombre in (("frio", "Frio"), ("caliente", "Caliente")):
    v = [float(r["arranque_s"]) for r in arr if r["caso"] == caso]
    m(f"arranque{nombre}", num(st.mean(v), "{:.0f}") if v else None)
descarga = [re.search(r"in ([\d.]+)(m?s)", r["descarga_evento"]) for r in arr if r["caso"] == "frio"]
descarga = [float(x.group(1)) / (1000 if x.group(2) == "ms" else 1) for x in descarga if x]
m("descarga", num(st.mean(descarga), "{:.0f}") if descarga else None)

# ---------------------------------------------------------------- drenado
dren = CLU / "evidencias" / "04-drenado" / "drenado.txt"
if dren.exists():
    t = dren.read_text(encoding="utf-8")
    nodo = re.search(r"kubectl drain (\S+)", t)
    expulsados = re.findall(r"pod/(\S+) evicted", t)
    # La salida, no la línea "$ kubectl ..." que la produjo
    estado = re.search(r"^completedIndexes=(\S*) failedIndexes=\[(.*?)\]", t, re.M)
    m("drenNodo", nodo.group(1) if nodo else None)
    m("drenExpulsados", str(len(expulsados)))
    m("drenIndices", ", ".join(sorted({re.search(r"-(\d+)-[a-z0-9]+$", x).group(1) for x in expulsados})) or "ninguno")
    m("drenCompletos", estado.group(1) if estado else None)
    m("drenFallidos", estado.group(2) or "vacío" if estado else None)
else:
    for k in ("drenNodo", "drenExpulsados", "drenIndices", "drenCompletos", "drenFallidos"):
        m(k, None)

# ---------------------------------------------------------------- escribir
with open(SALIDA, "w", encoding="utf-8") as f:
    f.write("% Generado por examen/reporte/llenar.py; no editar a mano\n")
    columnas = {"filasComparacion": 10, "filasCosto": 3, "filasNodos": 4}   # filas de tabla
    for k, v in macros.items():
        if v is None:
            v = f"\\pend{{{k}}}"
            if k in columnas:
                v = f"\\multicolumn{{{columnas[k]}}}{{c}}{{{v}}}\\\\"
        f.write(f"\\newcommand{{\\{k}}}{{{v}}}\n")
faltan = [k for k, v in macros.items() if v is None]
print(f"{SALIDA.relative_to(RAIZ)}: {len(macros) - len(faltan)} datos listos, {len(faltan)} pendientes")
if faltan:
    print("  pendientes:", ", ".join(faltan))
