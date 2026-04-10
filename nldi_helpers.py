"""
utils/nldi_helpers.py
---------------------
Wrappers around the pynhd NLDI API with disk caching.

All functions accept a ``cache_dir`` argument (default: ``"./cache/nldi"``).
Results are stored as GeoPackage files so repeated runs skip network calls.
"""

import os
import logging

import geopandas as gpd
from pynhd import NLDI

logger = logging.getLogger(__name__)
_nldi = NLDI()

DEFAULT_CACHE_DIR = "./cache/nldi"


def _cache_path(cache_dir: str, prefix: str, key: str) -> str:
    """Return a filesystem-safe cache path for a given prefix and key."""
    os.makedirs(cache_dir, exist_ok=True)
    safe_key = key.replace("-", "_").replace("/", "_")
    return os.path.join(cache_dir, f"{prefix}_{safe_key}.gpkg")


def fetch_basin(
    site_no: str,
    cache_dir: str = DEFAULT_CACHE_DIR,
) -> gpd.GeoDataFrame | None:
    """
    Fetch the upstream drainage basin polygon for a single USGS gauge site.

    Parameters
    ----------
    site_no : str
        NLDI-formatted site identifier, e.g. ``"USGS-05420500"``.
    cache_dir : str
        Directory to cache results. Created if it does not exist.

    Returns
    -------
    GeoDataFrame or None
        Basin polygon, or None if the request failed.
    """
    cache_file = _cache_path(cache_dir, "basin", site_no)
    if os.path.exists(cache_file):
        logger.debug("Cache hit: basin %s", site_no)
        return gpd.read_file(cache_file)

    try:
        basin = _nldi.get_basins(feature_ids=[site_no], fsource="nwissite")
        if basin is not None and not basin.empty:
            basin.to_file(cache_file, driver="GPKG")
            logger.info("Fetched and cached basin for %s", site_no)
            return basin
    except Exception as exc:
        logger.warning("Failed to fetch basin for %s: %s", site_no, exc)

    return None


def fetch_basins(
    site_numbers: list[str],
    cache_dir: str = DEFAULT_CACHE_DIR,
) -> dict[str, gpd.GeoDataFrame]:
    """
    Fetch upstream drainage basin polygons for multiple USGS gauge sites.

    Parameters
    ----------
    site_numbers : list of str
        NLDI-formatted site identifiers.
    cache_dir : str
        Directory to cache results.

    Returns
    -------
    dict
        Mapping of site_no → basin GeoDataFrame for all successful fetches.
    """
    return {
        site: basin
        for site in site_numbers
        if (basin := fetch_basin(site, cache_dir=cache_dir)) is not None
    }


def keep_largest_basin(
    group_sites,
    cache_dir: str = DEFAULT_CACHE_DIR,
) -> str | None:
    """
    Given a group of site IDs within the same HUC12, return the site with
    the largest upstream drainage basin area (i.e., the most downstream gauge).

    Parameters
    ----------
    group_sites : array-like of str
        Site IDs belonging to a single HUC12.
    cache_dir : str
        Directory to cache basin results.

    Returns
    -------
    str or None
        The site_no with the largest basin area, or None if no basins could
        be fetched.

    Notes
    -----
    Basin area is computed in the CRS returned by NLDI (WGS84 / EPSG:4326),
    which is not area-preserving. This is acceptable here because the purpose
    is relative comparison among gauges within the same small HUC12, not
    absolute area measurement.
    """
    basins = fetch_basins(list(group_sites), cache_dir=cache_dir)
    max_area = 0.0
    max_site = None

    for site, basin in basins.items():
        if not basin.empty:
            area = basin.geometry.area.iloc[0]
            if area > max_area:
                max_area = area
                max_site = site

    return max_site


def fetch_upstream_flowlines(
    site_no: str,
    cache_dir: str = DEFAULT_CACHE_DIR,
) -> gpd.GeoDataFrame | None:
    """
    Fetch main-stem and tributary upstream flowlines for a gauge site,
    returning them as a single combined GeoDataFrame.

    Parameters
    ----------
    site_no : str
        NLDI-formatted site identifier.
    cache_dir : str
        Directory to cache results.

    Returns
    -------
    GeoDataFrame or None
        Combined flowlines with a ``site_no`` column, or None on failure.
    """
    parts = []
    for nav, label in [
        ("upstreamMain", "mainstem"),
        ("upstreamTributaries", "tribs"),
    ]:
        cache_file = _cache_path(cache_dir, f"flowlines_{label}", site_no)
        if os.path.exists(cache_file):
            logger.debug("Cache hit: %s flowlines %s", label, site_no)
            gdf = gpd.read_file(cache_file)
        else:
            try:
                gdf = _nldi.navigate_byid(
                    fsource="nwissite",
                    fid=site_no,
                    navigation=nav,
                    source="flowlines",
                )
                gdf["site_no"] = site_no
                gdf.to_file(cache_file, driver="GPKG")
                logger.info("Fetched and cached %s flowlines for %s", label, site_no)
            except Exception as exc:
                logger.warning(
                    "Failed to fetch %s flowlines for %s: %s", label, site_no, exc
                )
                continue
        parts.append(gdf)

    if not parts:
        return None

    combined = gpd.pd.concat(parts, ignore_index=True)
    combined["site_no"] = site_no
    return combined


def fetch_all_upstream_flowlines(
    site_list: list[str],
    cache_dir: str = DEFAULT_CACHE_DIR,
) -> gpd.GeoDataFrame:
    """
    Fetch upstream flowlines for multiple sites, returning a single
    GeoDataFrame with a ``site_no`` column.

    Parameters
    ----------
    site_list : list of str
        NLDI-formatted site identifiers.
    cache_dir : str
        Directory to cache results.

    Returns
    -------
    GeoDataFrame
        All flowlines concatenated, with a ``site_no`` column.

    Raises
    ------
    ValueError
        If no flowlines could be fetched for any site.
    """
    parts = [
        gdf
        for site in site_list
        if (gdf := fetch_upstream_flowlines(site, cache_dir=cache_dir)) is not None
    ]

    if not parts:
        raise ValueError("No upstream flowlines could be fetched for any site.")

    return gpd.pd.concat(parts, ignore_index=True)
