"""
General utilities.
"""

# pylint: disable=logging-fstring-interpolation, invalid-name, missing-docstring

import logging

import certifi
import urllib3
import yaml
from yaml.error import YAMLError

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())


def load_config_file(config_file):
    logger.info("Loading config file.")

    try:
        with open(config_file) as config_str:
            config = yaml.load(config_str)
    except (IOError, FileNotFoundError):
        logger.error(f"Failed to open config file: {config_file}")
    except YAMLError:
        logger.error(f"Couldn't load config from YAML file: {config_file}")
    else:
        return config


def get_certs():
    pool_manager = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
    return pool_manager.connection_pool_kw.get('ca_certs')
