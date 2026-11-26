"""Compara el proyecto en kind contra el clúster real del examen.

Lee las tablas que genera scripts/analyze.py:
  resultados/tabla.csv                 (kind, una laptop)
  examen/resultados/tabla.csv          (k3s en 3 laptops)
y produce examen/resultados/comparacion.png (T, S y E en la misma figura) y
comparacion.md (tabla lado a lado con fotos por segundo).

Uso: python examen/comparar.py [--fotos 7390]
"""

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
ESTILO = {"kind": "--", "clúster": "-"}
COLOR = {"block": "#1f77b4", "lpt": "#2ca02c"}


def leer(ruta: Path) -> list[dict]:
    with open(ruta, newline="") as f:
        return [r for r in csv.DictReader(f) if r["estrategia"] in COLOR]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fotos", type=int, default=7390)
    a = ap.parse_args()

    datos = {"kind": leer(RAIZ / "resultados" / "tabla.csv"),
             "clúster": leer(RAIZ / "examen" / "resultados" / "tabla.csv")}

    fig, ejes = plt.subplots(1, 3, figsize=(15, 4.3))
    for donde, filas in datos.items():
        for e in COLOR:
            rs = sorted((r for r in filas if r["estrategia"] == e), key=lambda r: int(r["p"]))
            if not rs:
                continue
            p = [int(r["p"]) for r in rs]
            for eje, col in zip(ejes, ("T_s", "S", "E")):
                eje.plot(p, [float(r[col]) for r in rs], ESTILO[donde], marker="o",
                         color=COLOR[e], label=f"{donde} · {e}")
    pmax = max(int(r["p"]) for f in datos.values() for r in f)
    ejes[1].plot([1, pmax], [1, pmax], "k:", lw=1, label="ideal")
    ejes[0].set(title="Tiempo de pared", ylabel="T(p) [s]")
    ejes[1].set(title="Speedup", ylabel="S(p) [adimensional]")
    ejes[2].set(title="Eficiencia", ylabel="E(p) [adimensional]", ylim=(0, 1.1))
    for eje in ejes:
        eje.set(xlabel="p (pods simultáneos)")
        eje.set_xscale("log", base=2)
        eje.grid(alpha=0.3)
    ejes[1].legend(fontsize=8)
    fig.suptitle(f"kind (1 laptop) contra k3s (3 laptops) · Oxford-IIIT Pet, {a.fotos} fotos, 16 tareas")
    fig.tight_layout()
    salida = RAIZ / "examen" / "resultados"
    fig.savefig(salida / "comparacion.png", dpi=150)

    lineas = ["| Estrategia | p | T kind [s] | T clúster [s] | S kind | S clúster | "
              "E kind | E clúster | fotos/s kind | fotos/s clúster |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    idx = {(d, r["estrategia"], int(r["p"])): r for d, fs in datos.items() for r in fs}
    for e in COLOR:
        for p in sorted({k[2] for k in idx if k[1] == e}):
            k, c = idx.get(("kind", e, p)), idx.get(("clúster", e, p))

            def v(r, col, fmt="{:.2f}"):
                return fmt.format(float(r[col])) if r and r[col] != "" else "—"

            def fps(r):
                return f"{a.fotos / float(r['T_s']):.0f}" if r else "—"

            lineas.append(f"| {e} | {p} | {v(k, 'T_s')} | {v(c, 'T_s')} | {v(k, 'S')} | "
                          f"{v(c, 'S')} | {v(k, 'E')} | {v(c, 'E')} | {fps(k)} | {fps(c)} |")
    (salida / "comparacion.md").write_text("\n".join(lineas) + "\n")
    print("\n".join(lineas))


if __name__ == "__main__":
    main()
