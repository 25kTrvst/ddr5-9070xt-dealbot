from dealbot.classification import classify
from dealbot.config import Config
from dealbot.models import Candidate


def check() -> None:
    cfg = Config(discord_token="self-test")
    bad = [
        "Adapter for Minisforum AtomMan X7 Ti Intel Core Ultra 9 185H 32GB DDR5 1TB PC",
        "UPGRADE TO 32 GB RAM FROM 16 GB DDR5 FOR OUR PC'S UPGRADES ONLY",
        "Crucial 32GB DDR5 5600MHz SODIMM laptop memory",
    ]
    for index, title in enumerate(bad):
        c = Candidate("test", str(index), "ram", title, f"https://example.com/{index}", 60, condition="new")
        assert not classify(c, cfg).accepted, f"false positive escaped: {title}"
    good = Candidate("test", "good", "ram", "G.Skill 32GB (2x16GB) DDR5 6000MHz CL30 U-DIMM Memory Kit", "https://example.com/good", 130, condition="new")
    assert classify(good, cfg).accepted
    gpu = Candidate("test", "gpu", "gpu", "XFX Radeon RX 9070 XT 16GB GDDR6 Graphics Card", "https://example.com/gpu", 550, condition="new")
    assert classify(gpu, cfg).accepted
    print("DealBot V6 self-test passed: strict identity gates are working.")


if __name__ == "__main__": check()
