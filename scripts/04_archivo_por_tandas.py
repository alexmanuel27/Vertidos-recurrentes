"""Procesa el archivo completo (664 productos L1C R097) por tandas, borrando el crudo.

SE EJECUTA EN TU macOS, en el entorno 'acolite' (necesita red, ACOLITE y netCDF4):

    conda activate acolite
    python scripts/04_archivo_por_tandas.py --tanda 20 > tandas.log 2>&1

Por que por tandas: el crudo del archivo son ~465 GB y en el disco caben ~94. Cada tanda
baja N productos, y cada producto pasa por ACOLITE -> .npz -> se borran el .zip, el SAFE
descomprimido y los L1R/L2R/L2W. Lo que queda por escena es un .npz de ~8 MB.

Cada producto se corre en su PROPIA carpeta de trabajo (datos/trabajo/<producto>/), asi
que el L2W que se exporta es sin ambiguedad el de ese producto y borrar es borrar esa
carpeta entera.

REANUDABLE. Se puede cortar en cualquier momento (Ctrl-C, corte de luz, reinicio) y
volver a lanzar la misma linea: se salta
  - lo que ya tiene .npz en datos/productos/ (cada .npz guarda el nombre del L1C del que
    sale, 'producto_l1c'; los del piloto se reexportaron con 02_exportar_npz.py para
    que lo lleven),
  - lo que el registro da por fallido (salvo --reintentar-fallos).

SE PROCESAN TODOS LOS PRODUCTOS, TAMBIEN LOS REPETIDOS. En 26 fechas el catalogo trae dos
o tres L1C del mismo paso (el tile partido entre datastrips; p. ej. 20160115: uno de 34 MB
y otro de 728 MB). Cada trozo cubre una parte distinta de la ventana, y como el crudo se
borra, descartar uno aqui seria perder datos sin haberlo decidido. Cada trozo da su .npz;
como se combinan antes de la climatologia es una decision de metodo pendiente
(PROTOCOLO_CONGELADO.md, seccion 14, 27/09/2026).
Un .zip ya bajado no se vuelve a bajar. El .npz se escribe de forma atomica, asi que un
corte no deja una escena a medias que luego se tome por buena.

REGISTRO. datos/productos/registro_tandas.jsonl, una linea JSON por producto y intento:
estado (ok / fallo), etapa en la que fallo (descarga / acolite / exportar), motivo,
AOT, tiempos. Solo se anade, nunca se reescribe.

Los ajustes de ACOLITE son los CONGELADOS de src/acolite_io.AJUSTES (protocolo secc. 3):
este script no cambia nada del metodo, solo el orden de las operaciones y el borrado.
"""
import os, sys, json, time, glob, shutil, zipfile, argparse, importlib.util, re
from datetime import datetime, timezone

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import acolite_io, exportar

GB = 1e9
GB_POR_PRODUCTO = 1.0     # zip ~0,8 GB; el SAFE se descomprime de uno en uno


def cargar_descarga():
    """00_descarga_cdse.py empieza por cifra y no se puede importar con import."""
    spec = importlib.util.spec_from_file_location(
        "descarga_cdse", os.path.join(AQUI, "00_descarga_cdse.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def clave(nombre):
    """(satelite, AAAAMMDD) de un nombre L1C o de un fichero escrito por ACOLITE.

    En R097 hay como mucho un paso por satelite y dia, asi que la clave es unica.
      S2B_MSIL1C_20190305T160229_N0500_R097_...  -> ('S2B', '20190305')
      S2B_MSI_2019_03_05_16_16_56_T17QLF_L2W.npz  -> ('S2B', '20190305')
    """
    base = os.path.basename(nombre)
    m = re.search(r"_(\d{8})T\d{6}_", base)
    if m:
        return base[:3], m.group(1)
    m = re.search(r"_(\d{4})_(\d{2})_(\d{2})_\d{2}_\d{2}_\d{2}_", base)
    if m:
        return base[:3], "".join(m.groups())
    return None


def leer_registro(ruta):
    """Ultimo estado de cada producto. Tolera una ultima linea cortada."""
    estado = {}
    if os.path.exists(ruta):
        with open(ruta) as f:
            for linea in f:
                try:
                    r = json.loads(linea)
                except ValueError:
                    continue
                estado[r["producto"]] = r
    return estado


def anotar(ruta, **r):
    r["cuando"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(ruta, "a") as f:
        f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
        f.flush()
        os.fsync(f.fileno())


def exportados(carpeta):
    """Nombres L1C que ya tienen .npz. Un .npz sin 'producto_l1c' no cuenta: avisa."""
    hechos = set()
    for f in sorted(glob.glob(os.path.join(carpeta, "*.npz"))):
        l1c = exportar.producto_de(f)
        if l1c:
            hechos.add(l1c)
        else:
            print(f"  AVISO: {os.path.basename(f)} no dice de que L1C sale; "
                  f"reexporta con scripts/02_exportar_npz.py", flush=True)
    return hechos


def motivo_acolite(carpeta):
    """La razon por la que ACOLITE no llego a L2W, sacada de su propio log."""
    logs = glob.glob(os.path.join(carpeta, "*log_file.txt"))
    if not logs:
        return "ACOLITE no escribio log"
    lineas = [l.strip() for l in open(logs[0], errors="replace") if l.strip()]
    # ACOLITE no siempre vuelca al fichero las ultimas lineas; si no esta el blackfill,
    # no se inventa un motivo (las lineas 'ReadError' del log son su tanteo de formatos
    # de compresion, no un error).
    blackfill = [l for l in lineas if "blackfill" in l]
    return blackfill[-1][:300] if blackfill else "ver log en datos/acolite_logs"


class Token:
    """Token de CDSE pedido solo si hace falta bajar algo, y renovado por TIEMPO."""
    def __init__(self, mod):
        self.mod, self.tk, self.t = mod, None, 0.0

    def __call__(self, forzar=False):
        # 480 s y no 1200: con 1200 hubo 401 a mitad de tanda, asi que caduca antes.
        if forzar or self.tk is None or time.time() - self.t > 480:
            # Un corte de red (wifi, DNS) no debe matar el bucle: se espera y se reintenta.
            for _ in range(30):
                try:
                    self.tk, self.t = self.mod.token(), time.time()
                    break
                except self.mod.requests.exceptions.RequestException as e:
                    print(f"    sin red para pedir el token ({type(e).__name__}); "
                          f"reintento en 60 s", flush=True)
                    time.sleep(60)
            else:
                sys.exit("\nPARADA: 30 min sin red para hablar con CDSE. Relanza cuando vuelva.")
            print("    (token CDSE nuevo)", flush=True)
        return self.tk


def zip_valido(ruta, p):
    """Completo = mide lo que dice el catalogo (ContentLength) y el zip cierra bien.

    Una conexion que se corta sin error deja un fichero truncado que requests da por
    bueno; el tamano del catalogo lo delata (comprobado: coincide al byte en los 14
    productos del piloto).
    """
    if not os.path.exists(ruta):
        return False
    esperado = int(p.get("ContentLength") or 0)
    if esperado and os.path.getsize(ruta) != esperado:
        return False
    return zipfile.is_zipfile(ruta)


def borrar(ruta):
    if os.path.isdir(ruta):
        shutil.rmtree(ruta, ignore_errors=True)
    elif os.path.exists(ruta):
        os.remove(ruta)


def procesar(zipruta, nombre, a, limite):
    """ACOLITE + exportacion de un producto. Devuelve el registro (sin anotarlo)."""
    trabajo = os.path.join(a.trabajo, nombre)
    borrar(trabajo)
    os.makedirs(trabajo)
    r = {"producto": nombre}
    t0 = time.time()
    # ACOLITE sustituye sys.stdout por un 'tee' a su log y solo lo restaura si termina
    # bien. Si lanza una excepcion, el siguiente print escribe en el log de una carpeta
    # que ya hemos borrado y el bucle entero muere. Se restaura aqui siempre.
    salida, errores = sys.stdout, sys.stderr
    try:
        l2w = acolite_io.lanzar_acolite(zipruta, trabajo, limite, a.acolite_src)
    except (Exception, SystemExit) as e:
        r.update(estado="fallo", etapa="acolite", motivo=f"{type(e).__name__}: {e}"[:300])
        l2w = None
    finally:
        sys.stdout, sys.stderr = salida, errores
    r["t_acolite_s"] = round(time.time() - t0)

    if l2w is not None:
        if len(l2w) != 1:
            r.update(estado="fallo", etapa="acolite",
                     motivo=f"{len(l2w)} L2W; {motivo_acolite(trabajo)}")
        else:
            try:
                m = exportar.exportar(l2w[0], a.productos)
            except Exception as e:
                m = {"ok": False, "motivo": f"{type(e).__name__}: {e}"[:300]}
            if m["ok"]:
                r.update(estado="ok", npz=m["npz"], fecha=m["fecha"], aot_550=m["aot_550"])
            else:
                r.update(estado="fallo", etapa="exportar", motivo=m["motivo"])

    # Los logs y ajustes de ACOLITE son texto y pesan ~15 kB: se guardan como procedencia.
    dlog = os.path.join(a.logs, nombre)
    os.makedirs(dlog, exist_ok=True)
    for f in glob.glob(os.path.join(trabajo, "*.txt")):
        shutil.copy2(f, dlog)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tanda", type=int, default=20, help="productos por tanda")
    ap.add_argument("--max-tandas", type=int, default=0, help="0 = hasta acabar")
    ap.add_argument("--catalogo", default="datos/crudo/catalogo.json")
    ap.add_argument("--crudo", default="datos/crudo")
    ap.add_argument("--trabajo", default="datos/trabajo")
    ap.add_argument("--productos", default="datos/productos")
    ap.add_argument("--registro", default=None,
                    help="por defecto <productos>/registro_tandas.jsonl")
    ap.add_argument("--logs", default="datos/acolite_logs")
    ap.add_argument("--acolite-src", default="externo/acolite")
    ap.add_argument("--min-libre-gb", type=float, default=15,
                    help="margen libre que se exige ademas de lo que ocupa la tanda")
    ap.add_argument("--max-fallos-seguidos", type=int, default=8,
                    help="parar si fallan tantos seguidos: algo sistematico, no una escena")
    ap.add_argument("--reintentar-fallos", action="store_true")
    ap.add_argument("--conservar-fallidos", action="store_true",
                    help="no borrar el .zip de un producto que falla (para diagnosticarlo)")
    ap.add_argument("--solo", nargs="*", default=None,
                    help="restringir a productos cuyo nombre contenga alguna de estas cadenas")
    a = ap.parse_args()
    a.registro = a.registro or os.path.join(a.productos, "registro_tandas.jsonl")
    for d in (a.crudo, a.trabajo, a.productos, a.logs):
        os.makedirs(d, exist_ok=True)

    # Un solo proceso a la vez: dos bucles sobre las mismas carpetas se borrarian el crudo.
    # Si el cerrojo es de un proceso que ya no existe (corte de luz, kill -9), se retoma.
    cerrojo = os.path.join(a.trabajo, "EN_MARCHA.lock")
    if os.path.exists(cerrojo):
        texto = open(cerrojo).read().strip()
        try:
            os.kill(int(texto.split()[1]), 0)
            vivo = True
        except (ProcessLookupError, ValueError, IndexError):
            vivo = False
        except PermissionError:
            vivo = True
        if vivo:
            sys.exit(f"Ya hay un bucle en marcha ({texto}). Si no es asi, borra {cerrojo}.")
        print(f"  cerrojo de un proceso que ya no existe ({texto}): se retoma", flush=True)
        os.remove(cerrojo)
    try:
        fd = os.open(cerrojo, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, f"pid {os.getpid()} desde {datetime.now():%Y-%m-%d %H:%M}\n".encode())
        os.close(fd)
    except FileExistsError:
        sys.exit(f"Otro bucle acaba de arrancar ({open(cerrojo).read().strip()}).")
    try:
        ejecutar(a)
    finally:
        os.remove(cerrojo)


def ejecutar(a):
    desc = cargar_descarga()
    if os.path.exists(a.catalogo):
        prods = json.load(open(a.catalogo))
    else:
        prods = desc.catalogo()
        json.dump(prods, open(a.catalogo, "w"), indent=1)
    prods = [p for p in prods if f"_{desc.ORBITA}_" in p["Name"]]   # protocolo secc. 2
    prods.sort(key=lambda p: p["ContentDate"]["Start"])
    if a.solo:
        prods = [p for p in prods if any(s in p["Name"] for s in a.solo)]

    registro = leer_registro(a.registro)
    hechos = exportados(a.productos)

    # Limpieza de un corte anterior: carpetas de trabajo huerfanas, y crudo de productos
    # que ESTE bucle ya dejo exportados. El crudo del piloto (no esta en el registro) no
    # se toca.
    for d in glob.glob(os.path.join(a.trabajo, "*.SAFE")):
        borrar(d)
    for nombre in registro:
        z = os.path.join(a.crudo, nombre + ".zip")
        if os.path.exists(z) and nombre in hechos:
            print(f"  limpieza: borro crudo ya exportado {nombre[:44]}")
            borrar(z)

    pendientes, n_hechos, n_fallidos = [], 0, 0
    for p in prods:
        if p["Name"] in hechos:
            n_hechos += 1
        elif (registro.get(p["Name"], {}).get("estado") == "fallo"
              and registro[p["Name"]].get("etapa") != "descarga"   # la red se reintenta sola
              and not a.reintentar_fallos):
            n_fallidos += 1
        else:
            pendientes.append(p)
    tandas = [pendientes[i:i + a.tanda] for i in range(0, len(pendientes), a.tanda)]
    if a.max_tandas:
        tandas = tandas[:a.max_tandas]
    fechas = {clave(p["Name"]) for p in prods}
    if len(fechas) < len(prods):
        print(f"{len(prods) - len(fechas)} productos comparten fecha con otro (tile partido "
              f"entre datastrips): se procesan todos, cada uno a su .npz", flush=True)
    print(f"{len(prods)} productos {desc.ORBITA} | ya exportados {n_hechos} | fallidos "
          f"antes {n_fallidos} | pendientes {len(pendientes)} | tandas ahora {len(tandas)}"
          f" de {a.tanda}", flush=True)
    print("ajustes congelados:", acolite_io.AJUSTES, flush=True)

    # Sin credenciales no se puede bajar nada: mejor decirlo ahora que a mitad de tanda.
    por_bajar = [p for t in tandas for p in t
                 if not zip_valido(os.path.join(a.crudo, p["Name"] + ".zip"), p)]
    if por_bajar and not (os.environ.get("CDSE_USUARIO") and os.environ.get("CDSE_CLAVE")):
        sys.exit(f"Hay {len(por_bajar)} productos que bajar y faltan CDSE_USUARIO / "
                 f"CDSE_CLAVE en el entorno.")

    limite = acolite_io.limite_bahia()
    token = Token(desc)
    seguidos, t_ini, n_ok, n_fallo = 0, time.time(), 0, 0

    def contar(r):
        nonlocal seguidos, n_ok, n_fallo
        if r["estado"] == "ok":
            seguidos, n_ok = 0, n_ok + 1
        else:
            seguidos, n_fallo = seguidos + 1, n_fallo + 1
            if seguidos >= a.max_fallos_seguidos:
                sys.exit(f"\nPARADA: {seguidos} fallos seguidos. Eso es algo sistematico "
                         f"(credenciales, red, ACOLITE), no una escena mala. Mira el "
                         f"registro {a.registro}; al relanzar se reanuda donde estaba.")

    for it, tanda in enumerate(tandas, 1):
        libre = shutil.disk_usage(a.crudo).free / GB
        falta = len(tanda) * GB_POR_PRODUCTO + a.min_libre_gb
        if libre < falta:
            sys.exit(f"\nPARADA: {libre:.0f} GB libres y la tanda necesita ~{falta:.0f}. "
                     f"Libera espacio o baja --tanda.")
        print(f"\n=== tanda {it}/{len(tandas)}: {len(tanda)} productos, "
              f"{libre:.0f} GB libres ===", flush=True)

        # 1. Bajar la tanda entera.
        listos = []
        for p in tanda:
            nombre = p["Name"]
            z = os.path.join(a.crudo, nombre + ".zip")
            if zip_valido(z, p):
                listos.append((nombre, z, 0))
                print(f"  crudo ya estaba: {nombre[:52]}", flush=True)
                continue
            borrar(z)   # uno truncado de un corte: descargar() lo daria por bueno
            t0 = time.time()
            ruta, est = desc.descargar(p["Id"], nombre, a.crudo, token())
            if ruta is None and "401" in str(est):
                # Token caducado (p. ej. el Mac se durmio a mitad de descarga): uno nuevo.
                ruta, est = desc.descargar(p["Id"], nombre, a.crudo, token(forzar=True))
            if ruta is None or not zip_valido(ruta, p):
                if ruta is not None:
                    est = (f"zip incompleto o corrupto: {os.path.getsize(ruta)} bytes de "
                           f"{p.get('ContentLength')}")
                    borrar(ruta)
                r = {"producto": nombre, "estado": "fallo", "etapa": "descarga",
                     "motivo": str(est)[:300]}
                anotar(a.registro, **r)
                print(f"  DESCARGA FALLIDA {nombre[:44]}: {est}", flush=True)
                contar(r)
                continue
            mb = os.path.getsize(ruta) / 1e6
            print(f"  bajado {nombre[:52]}  {mb:.0f} MB en {time.time()-t0:.0f} s", flush=True)
            # descargar() devuelve un Path y ACOLITE hace len() de la entrada: str.
            listos.append((nombre, str(ruta), round(time.time() - t0)))

        # 2. ACOLITE -> .npz -> borrar, producto a producto.
        for nombre, z, t_bajada in listos:
            r = procesar(z, nombre, a, limite)
            r["t_descarga_s"] = t_bajada
            # Se borra ANTES de anotar: si se corta entre medias, el .npz ya existe y la
            # reanudacion lo salta; lo que no puede pasar es un 'ok' con el crudo aun vivo
            # y nadie que lo borre.
            borrar(os.path.join(a.trabajo, nombre))
            if r["estado"] == "ok" or not a.conservar_fallidos:
                borrar(z)
            anotar(a.registro, **r)
            if r["estado"] == "ok":
                hechos.add(nombre)
                print(f"  OK   {nombre[:52]}  AOT550={r['aot_550']:.3f}  "
                      f"ACOLITE {r['t_acolite_s']} s -> {r['npz']}", flush=True)
            else:
                print(f"  FALLO {nombre[:52]} [{r['etapa']}] {r['motivo']}", flush=True)
            contar(r)

        hechos_ahora = n_ok + n_fallo
        if hechos_ahora:
            seg = (time.time() - t_ini) / hechos_ahora
            quedan = len(pendientes) - hechos_ahora
            print(f"  -- llevados {hechos_ahora} en esta sesion ({n_ok} ok, {n_fallo} "
                  f"fallos), {seg/60:.1f} min/producto; quedan {quedan} "
                  f"(~{quedan*seg/3600:.1f} h)", flush=True)

    total = len(exportados(a.productos))
    print(f"\nFIN de esta sesion: {n_ok} ok, {n_fallo} fallos. Exportadas en total: "
          f"{total} escenas en {a.productos}/. Registro: {a.registro}")


if __name__ == "__main__":
    main()
