from tradingbot.config import TradingConfig
from tradingbot.main import run


if __name__ == "__main__":
    config = TradingConfig()
    for issue in config.validate():
        print(f"Warning: {issue}")
    run(config)
