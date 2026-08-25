from dealbot.classification import classify
from dealbot.config import Config
from dealbot.models import Candidate
from dealbot.scoring import make_deal, resale_profit

CFG = Config(discord_token="test")


def item(kind: str, title: str, price: float = 100, **kwargs) -> Candidate:
    return Candidate("fixture", kwargs.pop("source_id", "1"), kind, title, "https://example.com/item/1", price, **kwargs)


def test_real_32gb_desktop_ram_is_accepted():
    c = item("ram", "V-COLOR Manta XFinity RGB DDR5 32GB (16GBx2) 6000MHz CL30 U-DIMM Memory Kit", condition="new")
    result = classify(c, CFG)
    assert result.accepted and result.speed_mts == 6000 and result.capacity_gb == 32


def test_minisforum_adapter_false_positive_is_rejected():
    c = item("ram", "Adapter for Minisforum AtomMan X7 Ti Intel Core Ultra 9 185H 32GB DDR5 1TB PC", 61.98, condition="new")
    assert not classify(c, CFG).accepted


def test_upgrade_service_false_positive_is_rejected():
    c = item("ram", "UPGRADE TO 32 GB RAM FROM 16 GB DDR5 FOR OUR PC'S UPGRADES ONLY", 135, condition="new")
    assert not classify(c, CFG).accepted


def test_sodimm_and_slow_ram_are_rejected():
    assert not classify(item("ram", "Crucial 32GB DDR5 5600MHz SODIMM laptop memory", condition="new"), CFG).accepted
    assert not classify(item("ram", "Corsair 32GB (2x16GB) DDR5 4800MHz DIMM memory kit", condition="new"), CFG).accepted


def test_exact_gpu_and_gre_rejection():
    assert classify(item("gpu", "XFX Quicksilver AMD Radeon RX 9070 XT 16GB GDDR6 Graphics Card", 549.99, condition="new"), CFG).accepted
    assert not classify(item("gpu", "AMD Radeon RX 9070 GRE 16GB Graphics Card", 499, condition="new"), CFG).accepted


def test_gpu_accessory_open_box_and_bundle_rejected():
    assert not classify(item("gpu", "Waterblock for Radeon RX 9070 XT graphics card", 99, condition="new"), CFG).accepted
    assert not classify(item("gpu", "XFX Radeon RX 9070 XT 16GB Graphics Card Open Box", 450, condition="open box"), CFG).accepted
    assert not classify(item("gpu", "RX 9070 XT + motherboard bundle", 550, condition="new"), CFG).accepted


def test_first_observation_does_not_claim_insane_or_buy():
    c = item("gpu", "XFX Quicksilver AMD Radeon RX 9070 XT 16GB GDDR6 Graphics Card", 549.99, condition="new")
    cl = classify(c, CFG); deal = make_deal(c, cl, CFG, observations=0)
    assert deal.score <= 82 and deal.recommendation == "WAIT / WATCH"


def test_resale_uses_sold_comps_and_all_costs():
    c = item("ram", "Corsair 32GB 6000MHz DDR5 DIMM memory kit", 100, shipping=5, condition="new")
    median_sold, profit = resale_profit(c, [180, 190, 200], CFG)
    assert median_sold == 190 and 30 < profit < 40


def test_resale_requires_three_exact_model_comps():
    c = item("ram", "Corsair 32GB 6000MHz DDR5 DIMM memory kit", 100)
    assert resale_profit(c, [180, 190], CFG) == (None, None)
