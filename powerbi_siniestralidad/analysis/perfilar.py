"""Perfil y conciliación reproducibles de los Parquet originales."""
import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
db = duckdb.connect()
run = db.execute
names = {"s": "siniestros", "a": "actor_vial", "v": "vehiculos", "d": "diccionario"}
profile = {}
for alias, name in names.items():
    path = str(ROOT.parent / "data" / "processed" / f"{name}.parquet").replace("'", "''")
    run(f"CREATE VIEW {alias} AS SELECT * FROM read_parquet('{path}')")
    rows = run(f"SELECT count(*) FROM {alias}").fetchone()[0]
    cols = run(f"DESCRIBE {alias}").fetchall()
    profile[name] = {
        "filas": rows,
        "duplicados_exactos_excedentes": rows - run(f"SELECT count(*) FROM (SELECT DISTINCT * FROM {alias})").fetchone()[0],
        "columnas": [
            {"campo": col, "tipo": kind, "nulos": rows - present, "distintos_no_nulos": distinct,
             "minimo": low, "maximo": high}
            for col, kind, present, distinct, low, high in (
                (col, kind, *run(f'SELECT count("{col}"), count(DISTINCT "{col}"), min("{col}"), max("{col}") FROM {alias}').fetchone())
                for col, kind, *_ in cols
            )
        ],
    }

    if "fecha" in [col[0] for col in cols]:
        profile[name]["periodo"] = run(f"SELECT min(fecha), max(fecha) FROM {alias}").fetchone()

key = "source_year,codigo_siniestro"
run("CREATE VIEW eventos AS SELECT *, year(fecha) AS anio_evento FROM s QUALIFY row_number() OVER (PARTITION BY year(fecha),codigo_siniestro ORDER BY source_year DESC)=1")
run(f"CREATE VIEW actores AS SELECT DISTINCT a.* FROM a SEMI JOIN eventos USING ({key})")
run(f"CREATE VIEW vehiculos AS SELECT v.* FROM v SEMI JOIN eventos USING ({key})")
checks = {
    "clave_fuente_nula": "SELECT count(*) FROM s WHERE source_year IS NULL OR codigo_siniestro IS NULL OR fecha IS NULL",
    "clave_fuente_repetida": f"SELECT count(*)-count(DISTINCT ({key})) FROM s",
    "actores_huerfanos": f"SELECT count(*) FROM a ANTI JOIN s USING ({key})",
    "vehiculos_huerfanos": f"SELECT count(*) FROM v ANTI JOIN s USING ({key})",
    "referencias_actor_vehiculo_sin_match": f"SELECT count(*) FROM a ANTI JOIN v USING ({key},codigo_vehiculo) WHERE a.codigo_vehiculo IS NOT NULL",
    "siniestros": "SELECT count(*) FROM eventos",
    "registros_actor": "SELECT count(*) FROM actores",
    "registros_vehiculo": "SELECT count(*) FROM vehiculos",
    "lesionados": "SELECT count(*) FROM actores WHERE coalesce(gravedad_30d,gravedad_tradicional) IN ('HERIDO','HERIDO HOSPITALIZADO','HERIDO VALORADO')",
    "fallecidos": "SELECT count(*) FROM actores WHERE coalesce(gravedad_30d,gravedad_tradicional) IN ('MUERTO','MUERTA')",
    "georreferenciados": "SELECT count(*) FROM eventos WHERE latitud BETWEEN 4 AND 5 AND longitud BETWEEN -75 AND -73",
    "siniestros_fatales": "SELECT count(*) FROM eventos WHERE coalesce(gravedad_30d_nombre,gravedad_tradicional_nombre)='CON MUERTOS'",
    "eventos_sin_actor": f"SELECT count(*) FROM eventos ANTI JOIN actores USING ({key})",
    "eventos_sin_vehiculo": f"SELECT count(*) FROM eventos ANTI JOIN vehiculos USING ({key})",
}
result = {name: run(sql).fetchone()[0] for name, sql in checks.items()}
assert all(result[k] == 0 for k in ("clave_fuente_nula", "clave_fuente_repetida", "actores_huerfanos", "vehiculos_huerfanos"))
result["por_anio"] = run("SELECT anio_evento,count(*),count(latitud) FROM eventos GROUP BY 1 ORDER BY 1").fetchall()
result["claves_evento_repetidas"] = run("SELECT count(*),count(*) FILTER(WHERE formularios=1 AND faltantes=0) FROM (SELECT count(DISTINCT formulario) formularios,count(*)-count(formulario) faltantes FROM s GROUP BY year(fecha),codigo_siniestro HAVING count(*)>1)").fetchone()
assert result["claves_evento_repetidas"][0] == result["claves_evento_repetidas"][1]
for name, value in [("perfil", profile), ("conciliacion", result), ("diccionario", run("SELECT * FROM d").fetchall())]:
    (ROOT / "analysis" / f"{name}.json").write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str)+"\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False))
