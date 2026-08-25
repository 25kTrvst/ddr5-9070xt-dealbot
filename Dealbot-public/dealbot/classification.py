from __future__ import annotations

import re
from urllib.parse import urlparse

from .config import Config
from .models import Candidate, Classification

SYSTEM_WORDS = re.compile(r"\b(desktop pc|gaming pc|mini\s*pc|laptop|notebook|workstation|computer system|atomman|minisforum)\b", re.I)
ACCESSORY_WORDS = re.compile(r"\b(adapter|heatsink|heat spreader|cooler|waterblock|backplate|bracket|cable|riser|mount|replacement fan)\b", re.I)
SERVICE_WORDS = re.compile(r"\b(upgrade service|installation service|upgrade to|from 16\s*gb|for our pc|repair service)\b", re.I)
BUNDLE_WORDS = re.compile(r"\b(bundle|combo|motherboard\s*\+|with motherboard|cpu\s*\+|prebuilt)\b", re.I)
OPEN_BOX = re.compile(r"\b(open[ -]?box|used|pre-owned|refurb|renewed|seller refurbished)\b", re.I)
SPONSORED = re.compile(r"\bsponsored\b", re.I)

RAM_BRANDS = (
    "corsair", "g.skill", "gskill", "kingston", "crucial", "teamgroup", "team group",
    "patriot", "silicon power", "v-color", "vcolor", "adata", "xpg", "geil", "oloy",
    "mushkin", "pny", "lexar", "klevv", "thermaltake",
)
GPU_BRANDS = ("amd", "radeon", "xfx", "powercolor", "sapphire", "asrock", "asus", "gigabyte", "yeston")


def _all_text(c: Candidate) -> str:
    aspect_text = " ".join(v for values in c.aspects.values() for v in values)
    meta = " ".join(str(c.metadata.get(k, "")) for k in ("description", "subtitle", "seller", "listing_type"))
    return f"{c.title} {c.condition} {c.category_name} {aspect_text} {meta}".lower()


def _numbers(text: str, pattern: str) -> list[int]:
    return [int(x) for x in re.findall(pattern, text, re.I)]


def _model_key(candidate: Candidate) -> str:
    kind, text = candidate.kind, candidate.title
    for name, values in candidate.aspects.items():
        if name.lower() in {"mpn", "model", "model number", "manufacturer part number"} and values:
            value = re.sub(r"[^A-Z0-9-]", "", values[0].upper())
            if len(value) >= 4: return value[:80]
    for field in ("model", "upc"):
        value = re.sub(r"[^A-Z0-9-]", "", str(candidate.metadata.get(field, "")).upper())
        if len(value) >= 4: return value[:80]
    # Manufacturer part numbers are much safer than a fuzzy title. Exclude common capacities/speeds.
    tokens = re.findall(r"\b[A-Z0-9][A-Z0-9-]{5,}\b", text.upper())
    ignored = {"DDR5", "GDDR6", "PCIE", "EXPRESS", "6000MHZ", "5600MHZ", "6400MHZ", "5000MHZ",
               "GRAPHICS", "DESKTOP", "GAMING", "MEMORY", "RADEON"}
    useful = [t for t in tokens if t not in ignored and not re.fullmatch(r"\d+(GB|TB|MHZ)", t)
              and re.search(r"[A-Z]", t) and re.search(r"\d", t)]
    if useful:
        return useful[-1][:80]
    clean = re.sub(r"[^a-z0-9]+", " ", text.lower())
    brand = next((b.replace(" ", "") for b in (RAM_BRANDS if kind == "ram" else GPU_BRANDS) if b in clean), "unknown")
    core = "rx9070xt" if kind == "gpu" else "ddr5"
    return f"{brand}:{core}:{' '.join(clean.split()[:10])}"[:120]


def classify(candidate: Candidate, cfg: Config) -> Classification:
    text = _all_text(candidate)
    reasons: list[str] = []

    if candidate.currency.upper() != "USD":
        return Classification(False, 0, ["currency is not USD"])
    if candidate.price <= 0:
        return Classification(False, 0, ["invalid price"])
    if OPEN_BOX.search(text) or candidate.condition.lower() not in {"new", "new other", "unknown", ""}:
        return Classification(False, 0, ["not a new item"])
    if SPONSORED.search(text) or candidate.metadata.get("sponsored") is True:
        return Classification(False, 0, ["sponsored result"])
    if SYSTEM_WORDS.search(text):
        return Classification(False, 0, ["complete computer/system, not a standalone part"])
    if ACCESSORY_WORDS.search(text):
        return Classification(False, 0, ["accessory, not the target product"])
    if SERVICE_WORDS.search(text):
        return Classification(False, 0, ["upgrade/service listing"])
    if BUNDLE_WORDS.search(text):
        return Classification(False, 0, ["bundle/combo listing"])

    if candidate.kind == "gpu":
        if re.search(r"\b9070\s*gre\b", text, re.I):
            return Classification(False, 0, ["9070 GRE is not RX 9070 XT"])
        if not re.search(r"\b(?:rx|radeon)\s*[- ]?9070\s*xt\b", text, re.I):
            return Classification(False, 15, ["exact RX 9070 XT identity missing"])
        if not any(brand in text for brand in GPU_BRANDS):
            reasons.append("board-partner brand not recognized")
        if not re.search(r"\b(graphics card|video card|gpu|gddr6|16\s*gb)\b", text, re.I):
            return Classification(False, 45, ["standalone graphics-card evidence missing"])
        confidence = 94 if candidate.category_id == cfg.ebay_gpu_category_id else 90
        reasons.append("exact RX 9070 XT identity confirmed")
        return Classification(True, confidence, reasons, _model_key(candidate), capacity_gb=16)

    if "ddr5" not in text:
        return Classification(False, 10, ["DDR5 identity missing"])
    if re.search(r"\b(sodimm|so-dimm|laptop memory)\b", text, re.I):
        return Classification(False, 0, ["laptop/SODIMM memory rejected"])
    capacities = _numbers(text, r"\b(\d{1,3})\s*gb\b")
    if 32 not in capacities:
        return Classification(False, 40, ["32GB total capacity not confirmed"])
    if any(x >= 128 for x in capacities) or re.search(r"\b[1248]\s*tb\b", text, re.I):
        return Classification(False, 0, ["storage/system capacity detected"])
    if not (any(brand in text for brand in RAM_BRANDS) or re.search(r"\b(u-?dimm|dimm|288[ -]?pin|memory (kit|module)|2\s*x\s*16\s*gb|16\s*gb\s*x\s*2)\b", text, re.I)):
        return Classification(False, 45, ["standalone RAM-kit evidence missing"])
    speeds = _numbers(text, r"\b(\d{4,5})\s*(?:mhz|mt/s|mts)\b")
    speed = max([x for x in speeds if 4000 <= x <= 10000], default=None)
    if speed is None:
        return Classification(False, 55, ["RAM speed not confirmed"])
    if speed < cfg.ram_min_speed:
        return Classification(False, 0, [f"{speed} MT/s is below {cfg.ram_min_speed}"])
    cas = next(iter(_numbers(text, r"\bcl\s*(\d{2})\b")), None)
    kit = "2x16GB" if re.search(r"(?:2\s*x\s*16|16\s*gb\s*x\s*2|16gbx2)", text, re.I) else "32GB"
    confidence = 96 if candidate.category_id == cfg.ebay_ram_category_id else 91
    reasons.extend(["standalone 32GB DDR5 confirmed", f"speed {speed} MT/s confirmed"])
    return Classification(True, confidence, reasons, _model_key(candidate), speed, cas, kit, 32)


def retailer_from_url(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")
