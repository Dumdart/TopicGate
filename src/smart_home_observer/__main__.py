from smart_home_observer.core.config.config_loader import ConfigLoader

def run():
    config = ConfigLoader().load_config()

if __name__ == "__main__":
    run()
