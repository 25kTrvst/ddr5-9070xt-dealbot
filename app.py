from dealbot.config import Config
from dealbot.discord_app import run


if __name__ == "__main__":
    config = Config()
    issues = config.validate()
    if issues:
        raise SystemExit("Configuration error:\n- " + "\n- ".join(issues))
    run(config)
