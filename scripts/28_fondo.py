"""¿Se ve el fondo en los focos? (EXPLORATORIO). Definido en la fila del 18/11/2026 de la secc. 14, antes de calcularlo.

    VERTIDOS_PIXEL_M=10 python scripts/28_fondo.py --resultados resultados_10m --productos datos/productos_10m --nmin 10
    python scripts/28_fondo.py --resultados resultados --productos datos/productos_ndci --nmin 5 --borde     # 30 escenas, 20 m

Reflectancias de superficie (rhos) de ACOLITE: mediana por pixel y estacion de las escenas aceptadas y validas.
Focos = z_c >= 3,5 (secc. 23); profundidad = carta de 1887 (secc. 25); referencia = bahia a la misma distancia a costa (+-20 m),
a > 80 m de un foco y con profundidad +-0,25 m. (a) Spearman rojo-profundidad 0,5-3 m (en bruto y tras restar la mediana de la
banda de distancia de 40 m de la referencia); (b) razones espectrales de los focos frente a su referencia emparejada.
IC 95 % por bootstrap de bloques de 100 m (2000, semilla fija).
"""
import os, sys, json, argparse, importlib.util, warnings
import numpy as np
from scipy import ndimage
from scipy.stats import rankdata
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import anomalias, geo, escenas, climatologia

s_ = importlib.util.spec_from_file_location("bat", os.path.join(AQUI, "23_batimetria.py"))
bat = importlib.util.module_from_spec(s_); s_.loader.exec_module(bat)
SEMILLA, N_BOOT, BLOQUE_M, PROF_MIN, PROF_MAX, PROF_TOL, DIST_TOL, BANDA_M, LEJOS_M, N_REF_MIN = 20261118, 2000, 100, 0.5, 3.0, 0.25, 20, 40, 80, 30
NMIN_MITAD = 8   # variante cruzada (anadida el 18/11 tras ver la primera pasada): n_obs minimo por mitad y estacion


def spearman(x, y):
    if x.size < 10 or np.ptp(x) == 0 or np.ptp(y) == 0:
        return np.nan
    return float(np.corrcoef(rankdata(x), rankdata(y))[0, 1])


def boot_bloques(b, f, rng):
    u, inv = np.unique(b, return_inverse=True)
    grupos = np.split(np.argsort(inv), np.cumsum(np.bincount(inv))[:-1])
    a = np.array([f(np.concatenate([grupos[i] for i in rng.integers(0, len(grupos), len(grupos))])) for _ in range(N_BOOT)])
    a = a[np.isfinite(a)]
    return [round(float(np.percentile(a, 2.5)), 3), round(float(np.percentile(a, 97.5)), 3)] if a.size > 100 else None


def medianas(productos, acept, cl, agua, dist, claves, nmin, sl):
    """Mediana por pixel y estacion (recortada a la ventana sl) de cada banda, sobre las escenas validas."""
    cubos = {(est, h): {k: [] for k in claves} for est in ("seca", "lluviosa") for h in "TAB"}; usadas = {"seca": 0, "lluviosa": 0}; sin = 0
    for r in escenas.listar(productos):
        try:
            e = escenas.cargar(r, claves=("turbidez_dogliotti", "swir", "swir2", "verde", "nir") + tuple(k for k in claves if k not in ("verde", "nir")))
        except KeyError:
            sin += 1; continue
        if e["l1c"] not in acept:
            continue
        v, _ = escenas.validez(e, agua, dist); est = climatologia.estacion_de(e["fecha"]); usadas[est] += 1
        for k in claves:
            arr = np.where(v, e[k], np.nan)[sl].astype(np.float32)
            for h in ("T", "A" if e["fecha"].year <= 2020 else "B"):
                cubos[(est, h)][k].append(arr)
    med = {}
    for (est, h), cb in cubos.items():
        med[(est, h)] = {}; nm = nmin if h == "T" else NMIN_MITAD
        for k in claves:
            c = np.stack(cb[k])
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                m = np.nanmedian(c, axis=0)
            m[np.sum(np.isfinite(c), axis=0) < nm] = np.nan; med[(est, h)][k] = m
    return med, usadas, sin


def analizar(est, med, hot, ref_ok, prof, dist, filas, cols, bandas, rng):
    rho = {k: med[k] for k in bandas}
    valido = np.all([np.isfinite(rho[k]) & (rho[k] > 0) for k in bandas], axis=0) & np.isfinite(prof)
    en = (prof >= PROF_MIN) & (prof <= PROF_MAX)
    H, R = hot & valido & en, ref_ok & valido & en
    B = int(round(BLOQUE_M / geo.PIXEL_M)); bloque = (filas // B) * 100000 + cols // B
    res = {"n_calientes_0.5_3m": int(H.sum()), "n_referencia_0.5_3m": int(R.sum())}
    if H.sum() < 10 or R.sum() < 30:
        res["aviso"] = "muy pocos pixeles"; return res
    # (a) rojo frente a profundidad
    banda = np.floor(dist / BANDA_M).astype(int); medb = {}
    for kb in np.unique(banda[R]):
        medb[kb] = np.median(rho["rojo"][R & (banda == kb)])
    def resid(M):
        return rho["rojo"][M] - np.array([medb.get(kb, np.nan) for kb in banda[M]])
    out = {}
    for nombre, M in (("calientes", H), ("referencia", R)):
        d, rj, bl = prof[M], rho["rojo"][M], bloque[M]; rs = resid(M); ok = np.isfinite(rs)
        out[nombre] = {"n": int(M.sum()), "spearman_bruto": round(spearman(d, rj), 3),
                       "ic95_bruto": boot_bloques(bl, lambda i: spearman(d[i], rj[i]), rng),
                       "spearman_tras_restar_banda": round(spearman(d[ok], rs[ok]), 3),
                       "ic95_tras_restar_banda": boot_bloques(bl[ok], lambda i: spearman(d[ok][i], rs[ok][i]), rng),
                       "rojo_mediana": round(float(np.median(rj)), 4), "profundidad_mediana_m": round(float(np.median(d)), 2)}
    res["rojo_frente_a_profundidad"] = out
    # (b) forma espectral de cada foco frente a su referencia emparejada
    pares = [("verde", "rojo"), ("nir", "rojo")] + ([("borde", "rojo")] if "borde" in bandas else []) + [("rojo", None)]
    lr = {p: np.log(rho[p[0]] / rho[p[1]]) if p[1] else np.log(rho[p[0]]) for p in pares}
    Rm = ref_ok & valido; rd, rp = dist[Rm], prof[Rm]; o = np.argsort(rd); rd, rp = rd[o], rp[o]
    lr_ref = {p: lr[p][Rm][o] for p in pares}
    fil = np.where(H)
    exceso = {p: np.full(fil[0].size, np.nan) for p in pares}; omitidos = 0
    for n, (i, j) in enumerate(zip(*fil)):
        a, b = np.searchsorted(rd, [dist[i, j] - DIST_TOL, dist[i, j] + DIST_TOL])
        sel = np.abs(rp[a:b] - prof[i, j]) <= PROF_TOL
        if sel.sum() < N_REF_MIN:
            omitidos += 1; continue
        for p in pares:
            exceso[p][n] = lr[p][i, j] - np.median(lr_ref[p][a:b][sel])
    res["pixeles_calientes_sin_referencia_emparejada"] = omitidos
    bl = bloque[H]; prof_h = prof[H]; esp = {}
    for nom, m in (("0.5_2m", prof_h < 2.0), ("2_3m", prof_h >= 2.0)):
        for p in pares:
            x = exceso[p]; ok = m & np.isfinite(x)
            if ok.sum() < 10:
                esp[f"{nom}_{p[0]}/{p[1] or 1}"] = {"n": int(ok.sum()), "aviso": "muy pocos"}; continue
            xs, bs = x[ok], bl[ok]
            esp[f"{nom}_{p[0]}/{p[1] or 1}"] = {"n": int(ok.sum()), "dif_log_razon_mediana": round(float(np.median(xs)), 3),
                                          "ic95": boot_bloques(bs, lambda i: float(np.median(xs[i])), rng),
                                          "razon_foco_sobre_referencia": round(float(np.exp(np.median(xs))), 3)}
    res["forma_espectral_foco_menos_referencia_log"] = esp
    # lectura prefijada
    r = out["referencia"]; ic1, ic2 = r["ic95_bruto"], r["ic95_tras_restar_banda"]
    ve = lambda s, ic: s is not None and s <= -0.2 and ic is not None and ic[1] < 0
    res["referencia_informativa_sobre_fondo"] = bool(ve(r["spearman_bruto"], ic1) and ve(r["spearman_tras_restar_banda"], ic2))
    return res


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--resultados", default="resultados"); ap.add_argument("--productos", required=True)
    ap.add_argument("--nmin", type=int, required=True); ap.add_argument("--borde", action="store_true"); a = ap.parse_args()
    cl = np.load(os.path.join(a.resultados, "climatologia.npz"))
    agua, bahia, dist, ft500, x, y = cl["agua"].astype(bool), cl["bahia"].astype(bool), cl["distancia_costa_m"], cl["f_tierra_500m"], cl["x"], cl["y"]
    acept = set(str(p) for p in cl["productos_l1c"]); E, N = np.meshgrid(x, y)
    f = np.where((y >= geo.NORTE_MIN) & (y <= geo.NORTE_MAX))[0]; c = np.where((x >= geo.ESTE_MIN) & (x <= geo.ESTE_MAX))[0]
    sl = np.s_[f[0]:f[-1] + 1, c[0]:c[-1] + 1]
    claves = ("verde", "rojo", "nir") + (("borde",) if a.borde else ())
    med, usadas, sin = medianas(a.productos, acept, cl, agua, dist, claves, a.nmin, sl)
    print("escenas usadas", usadas, "sin la banda", sin, flush=True)
    prof = bat.profundidad_en_rejilla(E[sl], N[sl]); filas, cols = np.indices(prof.shape)
    r_px = int(round(bat.LEJOS_M / geo.PIXEL_M)); rng = np.random.default_rng(SEMILLA)
    res = {"resolucion_m": geo.PIXEL_M, "escenas_usadas": usadas, "escenas_sin_la_banda": sin, "n_obs_minimo": a.nmin, "bandas": list(claves), "estaciones": {}}
    cache = os.path.join(a.resultados, "zc_mitades.npz"); zc_ = np.load(cache) if os.path.exists(cache) else None
    res["cruzada"] = {}
    def preparar(zs, ev):
        hot_full = (zs >= anomalias.Z_C_MIN) & ev
        lejos = ~ndimage.binary_dilation(hot_full, iterations=r_px)
        return (hot_full & bahia)[sl], (bahia & ev & lejos & ~hot_full)[sl]
    for est in ("seca", "lluviosa"):
        zs, ev = bat.zc_estacion(cl, est, agua, bahia, dist, ft500); hot, ref_ok = preparar(zs, ev)
        res["estaciones"][est] = analizar(est, med[(est, "T")], hot, ref_ok, prof, dist[sl], filas, cols, list(claves), rng)
        print(est, json.dumps(res["estaciones"][est], ensure_ascii=False, indent=1), flush=True)
        if zc_ is None:
            continue
        for sel, ver in (("A", "B"), ("B", "A")):
            hot, ref_ok = preparar(zc_[f"{sel}_{est}_z"], zc_[f"{sel}_{est}_ev"].astype(bool))
            k = f"{est}_focos_de_{sel}_espectros_de_{ver}"
            res["cruzada"][k] = analizar(est, med[(est, ver)], hot, ref_ok, prof, dist[sl], filas, cols, list(claves), rng)
            print(k, json.dumps(res["cruzada"][k], ensure_ascii=False, indent=1), flush=True)
    json.dump(res, open(os.path.join(a.resultados, f"fondo_{int(geo.PIXEL_M)}m.json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
