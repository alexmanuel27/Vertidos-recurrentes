# Sentinel-2 turbidity-anomaly frequency map of Havana Bay (20 m, 2017-2025)

Public products of the project *Vertidos-recurrentes* (repository root: method, code and frozen protocol).
They are the exact files delivered on 2026-10-21 to the hydrodynamic-model study of the same bay
(code `scripts/11_entrega_modelo.py`; delivered with commits `dad5893` and `96d2944` of that delivery).
**Status:** preprint pending. This folder is a data descriptor; the full study is the manuscript.

**Contains modified Copernicus Sentinel data [2017-2025].**

## What the study found, in one paragraph

The preregistered detection method (protocol frozen 2026-09-15, commit `0eeeecd`) did **not** pass its own
falsification criterion 12.2: no recurrent site survives a 40 m shore margin (3 candidate sites at 0 m, 2 at 20 m,
0 from 40 m). The products below are therefore **descriptive**: a per-pixel frequency of positive turbidity
anomalies. They were not a preregistered output (they are exploratory analysis E1, flagged as such in
`resultados/exploratorio.json`) and they do not locate discharge points.

## Files

| File | Content |
|---|---|
| `rejilla.npz` | `persistencia` (detection frequency per pixel, NaN outside water or with `n_validas` = 0), `n_validas`, `n_anomalias`, `mascara_agua`, centres `e`, `n`, `umbral_anomalia`, `definicion`. Rows run south to north. Read with `numpy.load(..., allow_pickle=False)`. |
| `persistencia_anomalias.tif`, `mascara_agua.tif` | Same maps as GeoTIFF (north up, EPSG:32617, DEFLATE). |
| `costa.geojson` | Water polygons of the mask, EPSG:32617 (declared in member `crs`; not RFC 7946). |
| `escenas.csv` | One row per L1C product of the archive (664): UTC time, product name, level, OData URL, access date, tile cloud cover, valid-water fraction, used (0/1), reason for discarding. |
| `anomalias.nc` | Per-scene `z_t` and `anomalia_positiva` (113 x 253 x 238), CF-1.8. |
| `focos.csv` | Candidate foci with coordinates (see below). |
| `pixeles_comparacion_modelo.csv` | The 8908 pixels used by the model comparison, with block id. |
| `SHA256SUMS` | Checksums of all files here. |

## Definitions

- **Product and level.** Sentinel-2 MSI L1C, tile T17QLF, relative orbit R097 only (R054 does not cover the bay).
  Copernicus Data Space Ecosystem, OData catalogue queried 2026-09-16; downloads 2026-09-16 to 2026-10-03.
  Archive: 664 products, 637 acquisitions, 2016-01-15 to 2025-12-28.
- **Atmospheric correction and turbidity.** ACOLITE dark spectrum fitting (clone `d61c8de`), fixed AOT per scene,
  residual glint correction, 20 m. Turbidity (FNU) from Dogliotti et al. (2015), blended version; in the bay it is
  effectively the red-band branch (99.8 % of valid values < 16.4 FNU).
- **Acquisition time.** All 113 used scenes were acquired between **16:16 and 16:17 UTC** over the bay
  (`fecha_hora_utc` in `escenas.csv`). The datatake start in the product name is 10-17 min earlier and is not
  the time over the bay.
- **Cloud and scene filter.** No threshold on catalogue cloud cover (the tile value in `escenas.csv`, 0-60 % for
  the used scenes, median 6 %, is informative only and refers to the 100 x 100 km tile). One L1C product per
  pass (the one with the largest footprint on the window). A scene is **used** if its ACOLITE AOT is finite
  and at least 60 % of the window's water pixels are valid: 113 of 637 acquisitions (71 dry-season, 42 wet-season;
  none from 2016; per year 2017: 6, 2018: 13, 2019: 20, 2020: 12, 2021: 11, 2022: 14, 2023: 12, 2024: 8, 2025: 17).
- **Valid pixel in a scene.** Water; finite turbidity; ACOLITE `l2_flags` bits 1-4 clear (cirrus, high TOA,
  negative reflectance, out of scene); rho(2200 nm) <= 0.010 (haze test); outside the vessel mask (residual of the
  SWIR adjacency profile above the scene median + 6 MAD, dilated 2 px). No separate cloud mask is applied.
- **Water mask.** Median NDWI over the 637 acquisitions > 0, keeping only connected components that contain
  the bay or the open sea.
- **Baseline.** Per pixel and season (dry Nov-Apr, wet May-Oct): median and 1.4826 x MAD of valid turbidity
  over the **same 113 used scenes** (in-sample, so the scene under test contributes to its own baseline).
  A pixel is evaluable with >= 20 observations and MAD > 0. Computed and committed before any anomaly
  (commit `0dba286`, 2026-10-13).
- **Positive turbidity anomaly.** z_t >= 3.5 **and** z_s >= 3.0 (`umbral_anomalia = [3.5, 3.0]`), with
  z_t = (T - seasonal median) / (1.4826 MAD seasonal) and z_s = (T - median of the day) / (1.4826 MAD of the day)
  over the valid pixels of the window.
- **Frequency** (`persistencia` in `rejilla.npz`) = `n_anomalias` / `n_validas`, where `n_validas` is the number of
  used scenes in which the pixel is valid and evaluable. It pools dry and wet scenes. It is **not** the
  protocol's site persistence, which is computed on 40 m cells.
- **Grid.** Native project grid, not resampled: UTM zone 17N (EPSG:32617), 20 m, 238 columns x 253 rows, pixel
  edges E 361140-365900, N 2556340-2561400, centres E 361150 + 20 i, N 2556350 + 20 j.
  Water pixels: 11 287, of which 935 have `n_validas` = 0.

## Pixel list for the model comparison

`pixeles_comparacion_modelo.csv` holds the 8908 pixels in 145 blocks used by the companion hydrodynamic-model
study. Columns: `fila_j`, `col_i` (index on this grid, 0 = south-west), `E_utm17n`, `N_utm17n` (pixel centre),
`bloque` = (`fila_j` // 10) x 1000 + `col_i` // 10 (blocks of 10 x 10 pixels = 200 m), `n_validas`, `n_anomalias`,
`frecuencia`. A pixel is in the list if all of the following hold:

1. water in the satellite mask and in the model mask (the model mask is not part of this repository);
2. rows 0-251 only (the model grid has 252 rows; row 252 is dropped);
3. at least 2 pixels from land, implemented as two successive 4-neighbour erosions of the water mask. This keeps
   pixels whose centre is at least **44.7 m** (not exactly 40 m) from the nearest land-pixel centre; a plain
   Euclidean cut at 40 m would keep 9467 pixels instead of 8908;
4. `n_validas` >= 50 (this removes only 16 pixels, since the median over the list is 98 and the maximum 110).

The selection was reproduced with `pixeles()` of `scripts/comparacion_s2.py` of the model repository
(commit `0d37397`), which gives 8908 pixels and 145 blocks. The model and its comparison statistics belong
to that study and are not results of this one.

## Foci (`focos.csv`)

Nine rows in three classes; none is verified in the field yet.

1. Two preregistered recurrent-site candidates (east coast; entrance channel). Both fall outside the grid window,
   and neither survives the 40 m margin, so the preregistered method failed.
2. Three **exploratory** permanent foci (family E3), defined after looking at the data, so they are hypotheses
   only. Diagnostics of 2026-11-13 (`resultados/diagnosticos_sitios.json`, `lluvia_20m.json`):
   the head of the south arm (Guasabacoa) behaves like a land-adjacency signature (amplitude grows with the
   land fraction); the south-west arm (Atares) does not, has OpenStreetMap piers 30 and 52 m away (possible berth
   or moored-vessel effect) and is the only one of five foci whose anomalies track rainfall against matched
   controls (p = 0.027), which with five tests is not evidence by itself.
3. Four river or drain mouths from OpenStreetMap (Overpass query 2026-10-17, (c) OpenStreetMap contributors,
   ODbL). They are **not** turbidity detections.

## Limits that affect any use of the frequency map

- Adjacency: the fitted e-folding length of land contamination has median 45 m and 90th percentile 96 m
  (89 well-fitted scenes), longer than the 40 m shore margin.
- Only 18 % of acquisitions were usable; years are unequal and 2016 is absent.
- The baseline is in-sample and the per-pixel counts are small (maximum frequency in the comparison list 0.146).
- Pooling 71 dry and 42 wet scenes means the map is not a dry-season climatology.

## Reproduce

From the repository root, with the `acolite` conda environment and `datos/productos` (20 m products):

    python scripts/11_entrega_modelo.py --salida <folder>

Checked on 2026-11-14 at commit `bbb1973`: `rejilla.npz`, both GeoTIFF, `costa.geojson`, `escenas.csv` and
`focos.csv` are byte-identical to the files here; `anomalias.nc` has identical arrays and differs only in the
`history` attribute (date).

## Licences and attribution

Code: MIT (`../LICENSE`). Data products and this description: CC BY 4.0 (`../LICENSE-DATOS.md`).
Attribution: **Contains modified Copernicus Sentinel data [2017-2025]**. OpenStreetMap rows: ODbL.

## Citation

Preprint and repository URL: *pending* (to be filled when published).
