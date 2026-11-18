"""Peticion 2, bloque D: marea y viento a la hora de paso (EXPLORATORIO). Reglas: fila del 18/11/2026 de la secc. 14.

    ~/venvs/tide_pytmd/bin/python scripts/31_marea_viento.py                                            # 20 m
    VERTIDOS_PIXEL_M=10 ~/venvs/tide_pytmd/bin/python scripts/31_marea_viento.py --resultados resultados_10m

Entrada: resultados*/contraste_escenas_<res>m_2016_2025.csv (30_contraste_escenas.py). Marea: constantes armonicas de EOT20
(datos/marea/eot20_habana.json del repo del modelo, solo lectura; modelo libre de SEANOE, doi 10.17882/79489) interpoladas en la
boca (E 361000, N 2560900) y predichas con pyTMD (correcciones nodales 'FES'); sensibilidad con FES2022b (mismo formato; requiere
registro, no es el modelo principal). Viento: ERA5 horario 10 m (datos/forzamiento/era5 del modelo), punto de rejilla mas
cercano: velocidad a la hora de paso (interpolada linealmente entre horas) y media de las 24 h previas.
"""
import os, sys, csv, json, argparse, importlib.util
import numpy as np
from datetime import datetime, timedelta
from scipy.stats import spearmanr
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import geo

MODELO = "/Users/alex/Nube /repos/Modelo-hidrodin-mico/datos"
BOCA_UTM = (361000.0, 2560900.0)
SEMILLA, N_BOOT, N_MIN_ESTRATO = 20261118, 2000, 8


def carga(nombre):
    s = importlib.util.spec_from_file_location(nombre, os.path.join(AQUI, nombre + ".py"))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


grad = carga("24_gradiente")


def constantes(ruta, lat0, lon0):
    """Constantes complejas hc = A exp(-i fase) por constituyente: IDW (1/d^2) de los nodos validos de las 4 celdas vecinas."""
    d = json.load(open(ruta)); out = {}
    for c, v in d.items():
        lon, lat = np.array(v["lon"]), np.array(v["lat"]); A, F = np.array(v["amp_m"], float), np.array(v["fase_grados"], float)
        i0 = np.searchsorted(lon, lon0) - 1; j0 = np.searchsorted(lat, lat0) - 1
        num = 0j; den = 0.0
        for j in (j0, j0 + 1):
            for i in (i0, i0 + 1):
                if 0 <= j < lat.size and 0 <= i < lon.size and np.isfinite(A[j, i]):
                    w = 1.0 / (np.hypot(lat[j] - lat0, lon[i] - lon0) ** 2 + 1e-12); num += w * A[j, i] * np.exp(-1j * np.radians(F[j, i])); den += w
        if den > 0:
            out[c] = num / den
    return out


def predice(mjd, hc):
    from pyTMD.constituents import arguments
    cons = list(hc)
    pu, pf, G = arguments(np.atleast_1d(np.asarray(mjd, float)), cons, corrections="FES")
    th = np.radians(G) + pu
    return np.real(pf * np.array([hc[c] for c in cons])[None, :] * np.exp(1j * th)).sum(1)


def mjd_de(dt):
    return (dt - datetime(1858, 11, 17)).total_seconds() / 86400.0


class Viento:
    def __init__(self, lat0, lon0):
        self.lat0, self.lon0, self.cache = lat0, lon0, {}

    def mes(self, anio, mes):
        k = (anio, mes)
        if k not in self.cache:
            import netCDF4 as nc
            ds = nc.Dataset(f"{MODELO}/forzamiento/era5/era5_habana_{anio}{mes:02d}_instant.nc")
            la, lo = np.array(ds["latitude"][:]), np.array(ds["longitude"][:]); i = int(np.argmin(abs(la - self.lat0))); j = int(np.argmin(abs(lo - self.lon0)))
            t = np.array(ds["valid_time"][:], float); u = np.array(ds["u10"][:, i, j], float); v = np.array(ds["v10"][:, i, j], float)
            self.cache[k] = (t, u, v, (float(la[i]), float(lo[j])))
        return self.cache[k]

    def serie(self, dt):
        t, u, v, pt = [], [], [], None
        for d in (dt - timedelta(days=2), dt, dt + timedelta(days=1)):
            a, b, c, pt = self.mes(d.year, d.month); t.append(a); u.append(b); v.append(c)
        t, u, v = np.concatenate(t), np.concatenate(u), np.concatenate(v); o = np.argsort(t); t, u, v = t[o], u[o], v[o]
        _, ix = np.unique(t, return_index=True); return t[ix], u[ix], v[ix], pt

    def en(self, dt):
        t, u, v, pt = self.serie(dt); ts = (dt - datetime(1970, 1, 1)).total_seconds()
        up, vp = np.interp(ts, t, u), np.interp(ts, t, v); h = (t > ts - 24 * 3600 - 1) & (t <= ts)
        return float(np.hypot(up, vp)), float(np.mean(np.hypot(u[h], v[h]))), int(h.sum()), pt


def boot_mediana(x, rng):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    if x.size < 3:
        return None
    b = np.median(x[rng.integers(0, x.size, (N_BOOT, x.size))], axis=1); return [round(float(np.percentile(b, 2.5)), 3), round(float(np.percentile(b, 97.5)), 3)]


def estrato(filas, rng):
    r = {"n_escenas": len(filas)}
    for var in ("todos", "a100m"):
        med = {n: float(np.nanmedian([f[f"{n}_{var}"] for f in filas])) if filas else float("nan") for n in grad.ZN}
        o = grad.orden(med) if filas else None
        r[f"orden_{var}"] = o; r[f"bahia_menos_mar_{var}"] = round(max(med["marimelena"], med["bahia_centro_y_canal"]) - med["mar"], 3) if filas else None
        r[f"centro_menos_mar_{var}"] = round(med["bahia_centro_y_canal"] - med["mar"], 3) if filas else None
    d = np.array([f["d_focos"] for f in filas], float); d = d[np.isfinite(d)]
    r.update({"n_con_d": int(d.size), "d_mediana": round(float(np.median(d)), 3) if d.size else None, "d_ic95_bootstrap_escenas": boot_mediana(d, rng), "frac_d_mayor_0": round(float((d > 0).mean()), 3) if d.size else None})
    return r


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--resultados", default="resultados"); a = ap.parse_args()
    res_m = int(geo.PIXEL_M); rng = np.random.default_rng(SEMILLA)
    from pyproj import Transformer
    lon0, lat0 = Transformer.from_crs(32617, 4326, always_xy=True).transform(*BOCA_UTM)[0:2]
    hc = constantes(f"{MODELO}/marea/eot20_habana.json", lat0, lon0); hf = constantes(f"{MODELO}/marea/fes2022_habana.json", lat0, lon0)
    filas = list(csv.DictReader(open(os.path.join(a.resultados, f"contraste_escenas_{res_m}m_2016_2025.csv"))))
    vi = Viento(lat0, lon0); out = []
    for f in filas:
        dt = datetime.fromisoformat(f"{f['fecha']}T{f['hora_utc']}"); m = mjd_de(dt)
        h = float(predice(m, hc)[0]); dh = float(predice(m + 600 / 86400, hc)[0] - predice(m - 600 / 86400, hc)[0]); hF = float(predice(m, hf)[0]); dhF = float(predice(m + 600 / 86400, hf)[0] - predice(m - 600 / 86400, hf)[0])
        vp, v24, nh, pt = vi.en(dt)
        g = {k: (float(v) if k not in ("fecha", "hora_utc", "estacion", "l1c") else v) for k, v in f.items() if k != "anio"}
        g.update({"anio": int(f["anio"]), "marea_eot20_m": h, "marea_sube_eot20": dh > 0, "marea_fes2022_m": hF, "marea_sube_fes2022": dhF > 0, "viento_paso_ms": vp, "viento_24h_ms": v24, "n_horas_24h": nh})
        out.append(g)
    with open(os.path.join(a.resultados, f"marea_viento_escenas_{res_m}m.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    res = {"resolucion_m": res_m, "marea_modelo": "EOT20 (SEANOE doi 10.17882/79489), constantes extraidas por scripts/marea_eot20.py del repo del modelo en una malla de 0,125 grados (9 constituyentes: " + ", ".join(hc) + "), interpoladas por IDW en la boca; prediccion con pyTMD (nodal FES)",
           "marea_sensibilidad": "FES2022b (registro AVISO+; no es el modelo principal): " + ", ".join(hf), "boca_lat_lon": [round(lat0, 4), round(lon0, 4)], "viento_punto_era5": list(vi.serie(datetime(2020, 1, 15))[3]),
           "n_bootstrap": N_BOOT, "semilla": SEMILLA, "n_min_estrato": N_MIN_ESTRATO, "estaciones": {}}
    res["acuerdo_eot20_fes2022"] = {"corr_nivel": round(float(np.corrcoef([g["marea_eot20_m"] for g in out], [g["marea_fes2022_m"] for g in out])[0, 1]), 3),
                                    "concordancia_fase": round(float(np.mean([g["marea_sube_eot20"] == g["marea_sube_fes2022"] for g in out])), 3),
                                    "rango_eot20_m": [round(min(g["marea_eot20_m"] for g in out), 3), round(max(g["marea_eot20_m"] for g in out), 3)]}
    for est in ("seca", "lluviosa"):
        fe = [g for g in out if g["estacion"] == est]; d = {"n_escenas": len(fe), "estratos": {}, "spearman": {}}
        d["estratos"]["todas"] = estrato(fe, rng)
        mm, vp_, v24_ = np.median([g["marea_eot20_m"] for g in fe]), np.median([g["viento_paso_ms"] for g in fe]), np.median([g["viento_24h_ms"] for g in fe])
        d["medianas_corte"] = {"marea_m": round(float(mm), 3), "viento_paso_ms": round(float(vp_), 3), "viento_24h_ms": round(float(v24_), 3)}
        cortes = {"marea_alta": lambda g: g["marea_eot20_m"] >= mm, "marea_baja": lambda g: g["marea_eot20_m"] < mm,
                  "marea_subiendo": lambda g: g["marea_sube_eot20"], "marea_bajando": lambda g: not g["marea_sube_eot20"],
                  "viento_paso_alto": lambda g: g["viento_paso_ms"] >= vp_, "viento_paso_bajo": lambda g: g["viento_paso_ms"] < vp_,
                  "viento_24h_alto": lambda g: g["viento_24h_ms"] >= v24_, "viento_24h_bajo": lambda g: g["viento_24h_ms"] < v24_}
        for k, fn in cortes.items():
            d["estratos"][k] = estrato([g for g in fe if fn(g)], rng)
        ok = [g for g in fe if np.isfinite(g["d_focos"])]
        for nom, key in (("nivel_marea_eot20", "marea_eot20_m"), ("nivel_marea_fes2022", "marea_fes2022_m"), ("viento_paso", "viento_paso_ms"), ("viento_24h", "viento_24h_ms")):
            r = spearmanr([g[key] for g in ok], [g["d_focos"] for g in ok]); d["spearman"][nom] = {"n": len(ok), "rho": round(float(r.statistic), 3), "p": round(float(r.pvalue), 4)}
        res["estaciones"][est] = d
    json.dump(res, open(os.path.join(a.resultados, f"marea_viento_{res_m}m.json"), "w"), indent=1, ensure_ascii=False, default=lambda o: bool(o) if isinstance(o, (np.bool_,)) else float(o))
    print(json.dumps({k: res[k] for k in ("marea_modelo", "boca_lat_lon", "viento_punto_era5", "acuerdo_eot20_fes2022")}, ensure_ascii=False, indent=1))
    for est, d in res["estaciones"].items():
        print("==", est, d["n_escenas"], d["medianas_corte"], d["spearman"])
        for k, e in d["estratos"].items():
            print("  ", k, e["n_escenas"], "orden", [(e[f"orden_{v}"] or {}).get("cumple") for v in ("todos", "a100m")], "d", e["d_mediana"], e["d_ic95_bootstrap_escenas"], "bah-mar", e["bahia_menos_mar_todos"], e["bahia_menos_mar_a100m"])


if __name__ == "__main__":
    main()
