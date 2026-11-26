"""Une las partes que escribió cada pod.

Lee part-*.csv y part-*.json de la carpeta de salida y genera:
  resultados.csv  todas las fotos en una sola tabla
  summary.json    totales, tiempos por tarea y desbalance I = max(t_i) / promedio(t_i)
  mosaico.png     original | bordes de algunas fotos (si se guardaron los bordes)

Uso: python merge.py <carpeta_salida> [carpeta_entrada] [--tareas N]
"""

import argparse
import csv
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

LADO = 220      # tamaño de cada celda del mosaico
PARES = 12      # cuántas fotos aparecen en el mosaico
COLUMNAS = 4    # pares por fila


def unir_csv(salida: Path) -> list[dict]:
    filas = []
    for parte in sorted(salida.glob("part-*.csv")):
        with open(parte, newline="") as f:
            filas.extend(csv.DictReader(f))
    if filas:
        with open(salida / "resultados.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
            w.writeheader()
            w.writerows(filas)
    return filas


def resumir(salida: Path, filas: list[dict], tareas_esperadas: int | None) -> dict:
    partes = [json.loads(p.read_text()) for p in sorted(salida.glob("part-*.json"))]
    tiempos = [p["t_computo_s"] for p in partes]
    promedio = sum(tiempos) / len(tiempos) if tiempos else 0.0
    por_nodo: dict[str, int] = {}
    for p in partes:
        por_nodo[p["nodo"]] = por_nodo.get(p["nodo"], 0) + 1
    resumen = {
        "partes": len(partes),
        "partes_esperadas": tareas_esperadas,
        "completo": tareas_esperadas is None or len(partes) == tareas_esperadas,
        "estrategia": partes[0]["estrategia"] if partes else None,
        "fotos": len(filas),
        "errores": sum(1 for f in filas if f["estado"] != "ok"),
        "t_computo_total_s": round(sum(tiempos), 4),
        "t_max_s": round(max(tiempos), 4) if tiempos else 0.0,
        "t_min_s": round(min(tiempos), 4) if tiempos else 0.0,
        "t_promedio_s": round(promedio, 4),
        "desbalance_I": round(max(tiempos) / promedio, 4) if promedio else None,
        "tareas_por_nodo": por_nodo,
        "por_tarea": [
            {k: p[k] for k in ("indice", "nodo", "fotos", "bytes", "t_computo_s")}
            for p in partes
        ],
    }
    (salida / "summary.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False))
    return resumen


def mosaico(salida: Path, entrada: Path | None, filas: list[dict]) -> Path | None:
    carpeta_bordes = salida / "bordes"
    if not carpeta_bordes.is_dir():
        return None
    ok = [f for f in filas if f["estado"] == "ok"
          and (carpeta_bordes / (Path(f["archivo"]).stem + ".png")).exists()]
    if not ok:
        return None
    # Fotos repartidas a lo largo del lote, no solo las primeras
    paso = max(1, len(ok) // PARES)
    elegidas = ok[::paso][:PARES]
    filas_mosaico = (len(elegidas) + COLUMNAS - 1) // COLUMNAS
    lienzo = Image.new("RGB", (COLUMNAS * 2 * LADO, filas_mosaico * LADO), "#202020")
    dibujo = ImageDraw.Draw(lienzo)
    for k, f in enumerate(elegidas):
        x = (k % COLUMNAS) * 2 * LADO
        y = (k // COLUMNAS) * LADO
        if entrada is not None and (entrada / f["archivo"]).exists():
            with Image.open(entrada / f["archivo"]) as orig:
                orig = orig.convert("RGB")
                orig.thumbnail((LADO, LADO))
                lienzo.paste(orig, (x, y))
        with Image.open(carpeta_bordes / (Path(f["archivo"]).stem + ".png")) as b:
            b = b.convert("RGB")
            b.thumbnail((LADO, LADO))
            lienzo.paste(b, (x + LADO, y))
        dibujo.text((x + 4, y + 4), f"tarea {f['indice']}", fill="yellow")
    ruta = salida / "mosaico.png"
    lienzo.save(ruta)
    return ruta


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("salida", type=Path)
    ap.add_argument("entrada", type=Path, nargs="?")
    ap.add_argument("--tareas", type=int)
    a = ap.parse_args()

    filas = unir_csv(a.salida)
    if not filas:
        print(f"No hay partes en {a.salida}", file=sys.stderr)
        return 1
    r = resumir(a.salida, filas, a.tareas)
    m = mosaico(a.salida, a.entrada, filas)
    print(f"{r['partes']} partes, {r['fotos']} fotos, {r['errores']} errores, "
          f"I = {r['desbalance_I']}, nodos = {r['tareas_por_nodo']}")
    if m:
        print(f"Mosaico: {m}")
    return 0 if r["completo"] else 2


if __name__ == "__main__":
    sys.exit(main())
