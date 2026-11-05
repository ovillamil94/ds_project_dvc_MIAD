"""Genera un parquet SINTÉTICO con el esquema real del consolidado (solo para probar el código; no son datos reales)."""
import sys
import numpy as np
import pandas as pd


def make(n=12000, seed=0):
    r = np.random.default_rng(seed)
    anio = r.choice(np.arange(2019, 2026), n)
    hora = r.integers(0, 24, n)
    loc = r.choice(["KENNEDY", "SUBA", "USME", "CHAPINERO", "CIUDAD BOLIVAR", "ENGATIVA", "FONTIBON"], n)
    clase = r.choice(["CHOQUE", "ATROPELLO", "VOLCAMIENTO", "CAIDA DE OCUPANTE"], n, p=[.64, .26, .04, .06])
    vel = r.random(n) < .05
    z = -3.6 + 1.2 * (hora < 6) + 0.8 * (clase == "ATROPELLO") + 1.0 * (clase == "VOLCAMIENTO") + 1.5 * vel + 0.4 * (loc == "USME")
    fatal = r.random(n) < 1 / (1 + np.exp(-z))
    grav = np.where(fatal, "CON MUERTOS", "CON HERIDOS").astype(object)
    df = pd.DataFrame({
        "source_year": anio, "source_file": "x.xlsx", "codigo_siniestro": np.arange(n),
        "fecha": pd.to_datetime(anio.astype(str) + "-06-15"), "hora": pd.array(hora, dtype="Int64"), "minuto": 0,
        "anio": pd.array(anio, dtype="Int64"), "mes": pd.array(r.integers(1, 13, n), dtype="Int64"),
        "dia_semana": r.choice(["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO", "DOMINGO"], n),
        "localidad": loc, "latitud": 4.6 + r.normal(0, .05, n), "longitud": -74.1 + r.normal(0, .05, n),
        "clase_nombre": clase, "choque_nombre": "VEHICULO", "objeto_fijo_nombre": pd.NA,
        "gravedad_tradicional_nombre": np.where(anio >= 2025, None, grav),
        "gravedad_30d_nombre": np.where(anio >= 2022, grav, None),
        # como el consolidado real: solo se registra cuando es verdadera; en 2025 velocidad no existe
        "con_velocidad": pd.array(np.where(vel & (anio < 2025), 1.0, np.nan), dtype="float64"),
        "con_carga": pd.array(np.where(r.random(n) < .05, 1.0, np.nan), dtype="float64"),
    })
    df.loc[r.random(n) < .05, ["latitud", "longitud"]] = np.nan
    solo = df.sample(300, random_state=1).index
    df.loc[solo, ["gravedad_tradicional_nombre", "gravedad_30d_nombre"]] = "SOLO DANOS"
    return pd.concat([df, df.sample(500, random_state=2).assign(source_year=2024)], ignore_index=True)  # duplicados entre archivos


if __name__ == "__main__":
    make().to_parquet(sys.argv[1]); print("ok", sys.argv[1])
