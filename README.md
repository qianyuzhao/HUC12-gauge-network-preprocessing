# HUC12 River Network and Gauge Station Preprocessing

This repository prepares a topologically correct HUC12 watershed network for the
Upper Mississippi River Basin (UMRB), with gauge stations properly assigned for
use in nutrient export modeling.

## Citation

If you use this pipeline, please cite the associated manuscript
(Zhao, Q., Peng, B., Ma, Z., Jia, M., McIsaac, G. F., Robertson, D. M., ... & Guan, K. (2025). How do Hydrological Variability and Human Activities Control the Spatiotemporal Changes of Riverine Nitrogen Export in the Upper Mississippi River Basin?. Environmental Science & Technology, 60(1), 1028-1039.).

Any question? Email to qz29@illinois.edu

## Scientific Motivation

Standard NHD WBD HUC12 boundaries do not align perfectly with USGS gauge drainage
basins. When a gauge sits mid-polygon, the HUC12 it falls in may receive flow from
upstream HUC12s that bypass that gauge entirely. Naively assigning loads to such a
gauge inflates apparent nitrogen export. This pipeline:

1. Deduplicates HUC12 geometries in the WBD shapefile
2. Assigns one gauge per HUC12 — the most downstream one
3. **Splits HUC12 polygons** at the gauge's drainage basin boundary when the gauge
   does not drain the full polygon (default threshold: < 95% area overlap)
4. Re-routes upstream HUC12s that do not flow through the gauge to bypass it in
   the network topology

The result is a modified HUC12 shapefile with a corrected `HU_12_DS` (downstream
HUC12) field suitable for accumulation-based load modeling.

## Repository Structure

```
huc12_network_prep/
├── README.md
├── utils/
│   └── nldi_helpers.py              # NLDI API wrappers with disk caching
├── 01_clean_huc12.ipynb             # Deduplicate WBD HUC12 geometries
├── 02_assign_gauges.ipynb           # Filter gauges, spatial join to HUC12s
├── 03_split_polygons.ipynb          # Split HUC12s at gauge drainage boundaries
├── 04_fix_routing.ipynb             # Correct upstream routing for split polygons
└── environment.yml
```

## Required Inputs

| File | Description |
|------|-------------|
| `/WBD_Subwatershed.shp` | NHD WBD HUC12 shapefile |
| `/WRTDS/load_cal_year_clean.csv` | Annual nitrogen loads from WRTDS |
| `gaugeSiteInfoUMRB.csv` | USGS gauge metadata (site_no, lat/lon, drainage area) |

## Outputs

| File | Description |
|------|-------------|
| `/UMRB_HUC12_modified.shp` | Deduplicated UMRB HUC12 geometries |
| `/UMRB_HUC12_with_sites_modified.shp` | Final network with gauge assignments, split polygons, and corrected routing |

> **Note on 13-digit HUC12 codes:** Split "remainder" polygons (the portion of a
> HUC12 outside a gauge's drainage basin) receive a synthetic 13-character code
> formed by appending `"0"` to the original 12-digit code (e.g., `"070900010206"`
> → `"0709000102060"`). This is a local convention and not a standard NHD identifier.

## Gauge Filtering

Only gauges with complete annual load records for **both** time windows are retained:
- Early period: 2001–2005
- Late period: 2016–2020

These windows correspond to the pre/post comparison in the associated nitrogen
export trend analysis.

## Usage

1. Edit the `# === USER SETTINGS ===` block at the top of each notebook to set
   your local data paths. That is the only thing you need to change.
2. Run notebooks in order: `01 → 02 → 03 → 04`.

NLDI API results are cached to `cache/nldi/` to avoid redundant network calls
on re-runs.

## Dependencies

```bash
conda env create -f environment.yml
conda activate huc12_prep
```
