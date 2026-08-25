from __future__ import annotations

from .adorama import AdoramaParser
from .antonline import AntonlineParser
from .base import StoreParser
from .bestbuy_page import BestBuyPageParser
from .bh import BHPhotoParser
from .central_computers import CentralComputersParser
from .microcenter import MicroCenterParser
from .newegg import NeweggParser

_PARSERS: dict[str, type[StoreParser]] = {
    "Newegg": NeweggParser,
    "Best Buy page": BestBuyPageParser,
    "B&H": BHPhotoParser,
    "Micro Center": MicroCenterParser,
    "Adorama": AdoramaParser,
    "Central Computers": CentralComputersParser,
    "Antonline": AntonlineParser,
}


def get_parser(store_name: str) -> StoreParser:
    return _PARSERS.get(store_name, StoreParser)()
