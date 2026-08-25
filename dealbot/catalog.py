from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Candidate, Kind


@dataclass(slots=True, frozen=True)
class CatalogEntry:
    kind: Kind
    brand: str
    model_name: str
    model_number: str  # manufacturer part number (MPN)
    upc: str = ""
    speed_mts: int | None = None
    capacity_gb: int | None = None

    @property
    def model_key(self) -> str:
        return f"{self.brand.upper()}:{self.model_number.upper()}"


# Model numbers below are the manufacturer's own published MPNs for standalone
# RX 9070 XT board-partner cards and 32GB (2x16GB) DDR5 desktop kits at each
# speed tier this bot tracks. UPCs are intentionally left blank: they vary by
# region/revision and a wrong one would falsely "confirm" the wrong product,
# which is worse than not having it. Add UPCs you have personally verified
# from a retailer or manufacturer page for your region.
GPU_CATALOG: tuple[CatalogEntry, ...] = (
    CatalogEntry("gpu", "Sapphire", "Pulse RX 9070 XT", "11348-01-20G"),
    CatalogEntry("gpu", "Sapphire", "Nitro+ RX 9070 XT", "11348-02-20G"),
    CatalogEntry("gpu", "PowerColor", "Reaper RX 9070 XT", "RX9070XT16GB-E/OC"),
    CatalogEntry("gpu", "PowerColor", "Hellhound RX 9070 XT", "RX9070XT16G-L/OC"),
    CatalogEntry("gpu", "XFX", "Swift RX 9070 XT", "RX-97TSWFDU"),
    CatalogEntry("gpu", "XFX", "Quicksilver RX 9070 XT", "RX-97TQIFDU"),
    CatalogEntry("gpu", "ASRock", "Steel Legend RX 9070 XT", "RX9070XT SL 16GO"),
    CatalogEntry("gpu", "ASRock", "Taichi RX 9070 XT", "RX9070XT TAICHI OC 16GO"),
    CatalogEntry("gpu", "Gigabyte", "Gaming OC RX 9070 XT", "GV-R9070XTGAMING OC-16GD"),
    CatalogEntry("gpu", "Asus", "Prime RX 9070 XT", "PRIME-RX9070XT-O16G"),
)

RAM_CATALOG: tuple[CatalogEntry, ...] = (
    CatalogEntry("ram", "Corsair", "Vengeance 32GB (2x16GB) DDR5 5200MHz CL40", "CMK32GX5M2B5200C40", speed_mts=5200, capacity_gb=32),
    CatalogEntry("ram", "Corsair", "Vengeance 32GB (2x16GB) DDR5 5600MHz CL36", "CMK32GX5M2B5600C36", speed_mts=5600, capacity_gb=32),
    CatalogEntry("ram", "Corsair", "Vengeance 32GB (2x16GB) DDR5 6000MHz CL30", "CMK32GX5M2B6000C30", speed_mts=6000, capacity_gb=32),
    CatalogEntry("ram", "Corsair", "Dominator Platinum 32GB (2x16GB) DDR5 6400MHz CL32", "CMT32GX5M2X6400C32", speed_mts=6400, capacity_gb=32),
    CatalogEntry("ram", "G.Skill", "Flare X5 32GB (2x16GB) DDR5 5200MHz CL36", "F5-5200J3636C16GX2-FX5", speed_mts=5200, capacity_gb=32),
    CatalogEntry("ram", "G.Skill", "Flare X5 32GB (2x16GB) DDR5 6000MHz CL36", "F5-6000J3636C16GX2-FX5", speed_mts=6000, capacity_gb=32),
    CatalogEntry("ram", "G.Skill", "Trident Z5 Neo 32GB (2x16GB) DDR5 6000MHz CL30", "F5-6000J3040F16GX2-TZ5N", speed_mts=6000, capacity_gb=32),
    CatalogEntry("ram", "G.Skill", "Trident Z5 RGB 32GB (2x16GB) DDR5 6400MHz CL32", "F5-6400J3239F16GX2-TZ5RK", speed_mts=6400, capacity_gb=32),
    CatalogEntry("ram", "Kingston", "FURY Beast 32GB (2x16GB) DDR5 5600MHz CL36", "KF556C36BBEK2-32", speed_mts=5600, capacity_gb=32),
    CatalogEntry("ram", "Kingston", "FURY Beast 32GB (2x16GB) DDR5 6000MHz CL36", "KF560C36BBEK2-32", speed_mts=6000, capacity_gb=32),
    CatalogEntry("ram", "Kingston", "FURY Renegade 32GB (2x16GB) DDR5 6400MHz CL32", "KF564C32RSK2-32", speed_mts=6400, capacity_gb=32),
    CatalogEntry("ram", "Crucial", "Pro 32GB (2x16GB) DDR5 5600MHz CL46", "CP2K16G56C46U5", speed_mts=5600, capacity_gb=32),
    CatalogEntry("ram", "TeamGroup", "T-Force Delta RGB 32GB (2x16GB) DDR5 6000MHz CL38", "FF3D532G6000HC38ADC01", speed_mts=6000, capacity_gb=32),
    CatalogEntry("ram", "TeamGroup", "T-Create Expert 32GB (2x16GB) DDR5 6400MHz CL34", "CTCED532G6400HC34ADC01", speed_mts=6400, capacity_gb=32),
    CatalogEntry("ram", "Patriot", "Viper Venom 32GB (2x16GB) DDR5 6000MHz CL30", "PVV432G600C30K", speed_mts=6000, capacity_gb=32),
)


def _normalize(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def _find_by_upc(catalog: tuple[CatalogEntry, ...], upc: str) -> CatalogEntry | None:
    key = _normalize(upc)
    if not key:
        return None
    return next((e for e in catalog if e.upc and _normalize(e.upc) == key), None)


def _find_by_model_number(catalog: tuple[CatalogEntry, ...], value: str) -> CatalogEntry | None:
    key = _normalize(value)
    if len(key) < 4:
        return None
    return next((e for e in catalog if _normalize(e.model_number) == key), None)


def lookup(candidate: Candidate) -> CatalogEntry | None:
    catalog = GPU_CATALOG if candidate.kind == "gpu" else RAM_CATALOG
    upc = str(candidate.metadata.get("upc", ""))
    if upc:
        hit = _find_by_upc(catalog, upc)
        if hit:
            return hit
    model = str(candidate.metadata.get("model", ""))
    if model:
        hit = _find_by_model_number(catalog, model)
        if hit:
            return hit
    for name, values in candidate.aspects.items():
        if name.lower() in {"mpn", "model", "model number", "manufacturer part number"}:
            for value in values:
                hit = _find_by_model_number(catalog, value)
                if hit:
                    return hit
    return None
