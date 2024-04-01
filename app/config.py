import json

def load_instance_config():
    config = json.load(open('instance/config.json', 'r'))
    secrets = json.load(open('instance/secret.json', 'r'))
    return config, secrets
