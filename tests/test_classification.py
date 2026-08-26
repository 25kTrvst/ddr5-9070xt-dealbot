from dealbot.catalog import lookup as catalog_lookup
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


def test_catalog_match_boosts_confidence_and_sets_deterministic_model_key():
    c = item("ram", "Corsair Vengeance 32GB (2x16GB) DDR5 6000MHz CL30 memory kit", 130,
             metadata={"model": "CMK32GX5M2B6000C30"})
    result = classify(c, CFG)
    assert result.accepted and result.confidence >= 97 and result.model_key == "CORSAIR:CMK32GX5M2B6000C30"
    assert catalog_lookup(c) is not None


def test_ram_queries_cover_every_configured_speed_tier():
    cfg = Config(discord_token="test", ram_min_speed=5000, ram_capacities_gb=(32,))
    assert cfg.ram_queries == tuple(f"32GB DDR5 desktop memory {s}MHz" for s in (5000, 5200, 5600, 6000, 6400))


def test_ram_queries_drop_speeds_below_the_configured_minimum():
    cfg = Config(discord_token="test", ram_min_speed=5600)
    assert all(s >= 5600 for s in cfg.ram_speeds)


def test_default_capacity_behavior_is_unchanged():
    c = item("ram", "Corsair 32GB (2x16GB) DDR5 6000MHz DIMM memory kit", 130)
    result = classify(c, CFG)
    assert result.accepted and result.capacity_gb == 32


def test_configured_capacity_other_than_32gb_is_accepted():
    cfg = Config(discord_token="test", ram_capacities_gb=(32, 64))
    c = item("ram", "Corsair Vengeance 64GB (2x32GB) DDR5 6000MHz CL30 memory kit", 220)
    result = classify(c, cfg)
    assert result.accepted and result.capacity_gb == 64 and result.kit_config == "2x32GB"


def test_capacity_not_in_configured_list_is_rejected():
    cfg = Config(discord_token="test", ram_capacities_gb=(32,))
    c = item("ram", "Corsair 64GB (2x32GB) DDR5 6000MHz DIMM memory kit", 220)
    assert not classify(c, cfg).accepted


def test_second_gpu_model_disabled_by_default():
    c = item("gpu", "Sapphire Nitro+ AMD Radeon RX 7900 XTX 24GB GDDR6 Graphics Card", 650, condition="new")
    assert not classify(c, CFG).accepted


def test_second_gpu_model_accepted_when_enabled_with_its_own_price_ceiling():
    cfg = Config(discord_token="test", gpu2_enabled=True, gpu2_label="RX 7900 XTX", gpu2_max_price=700)
    c = item("gpu", "Sapphire Nitro+ AMD Radeon RX 7900 XTX 24GB GDDR6 Graphics Card", 650, condition="new")
    result = classify(c, cfg)
    assert result.accepted and result.identity_label == "RX 7900 XTX" and result.capacity_gb == 24
    assert cfg.gpu_price_ceiling("RX 7900 XTX") == 700
    assert cfg.gpu_price_ceiling("RX 9070 XT") == cfg.gpu_max_price


def test_9070_xt_still_works_and_gre_still_rejected_with_second_gpu_enabled():
    cfg = Config(discord_token="test", gpu2_enabled=True)
    assert classify(item("gpu", "XFX Radeon RX 9070 XT 16GB GDDR6 Graphics Card", 549.99, condition="new"), cfg).accepted
    assert not classify(item("gpu", "AMD Radeon RX 9070 GRE 16GB Graphics Card", 499, condition="new"), cfg).accepted


def test_16gb_kit_is_tracked_by_default_alongside_32gb():
    c = item("ram", "Patriot Viper Elite 5 16GB DDR5 6000MHz CL30 memory module", 45, condition="new")
    result = classify(c, CFG)
    assert result.accepted and result.capacity_gb == 16


def test_expanded_ram_brand_list_recognizes_sub_brand_names():
    c = item("ram", "HyperX Fury 32GB (2x16GB) DDR5 6000MHz DIMM Desktop Memory", 130, condition="new")
    assert classify(c, CFG).accepted


def test_second_slickdeals_feed_slot_is_optional_and_additive():
    from dealbot.sources.discovery import SlickdealsDiscovery

    cfg_none = Config(discord_token="test")
    assert not SlickdealsDiscovery(cfg_none).configured

    cfg_one = Config(discord_token="test", slickdeals_feed_url="https://example.com/a")
    assert cfg_one.slickdeals_feed_urls == ("https://example.com/a",)

    cfg_two = Config(discord_token="test", slickdeals_feed_url="https://example.com/a", slickdeals_feed_url_2="https://example.com/b")
    assert cfg_two.slickdeals_feed_urls == ("https://example.com/a", "https://example.com/b")
    assert SlickdealsDiscovery(cfg_two).configured
