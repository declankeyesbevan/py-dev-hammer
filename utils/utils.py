"""Useful utilities."""

import argparse
import logging
import time

from io import BytesIO

import boto3
import certifi
import urllib3
import yaml

from boto3.dynamodb.conditions import Key
from botocore.client import Config
from botocore.exceptions import ClientError
from botocore.vendored.requests.exceptions import SSLError
from yaml.error import YAMLError

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())


def argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-c', '--config', default='user_config.yml', help="Path to YAML configuration file.")
    return parser.parse_args()


def load_config_file(config_file='user_config.yml'):
    """
    Load config from a YAML file.
    :param config_file: String of path and name to configuration YAML
    :return: Dictionary of config for other functions and methods to use
    """
    logger.info("Loading config file.")

    try:
        with open(config_file) as config_str:
            config = yaml.load(config_str)
    except (IOError, FileNotFoundError):
        logger.exception("Failed to open config file: %s", config_file)
    except YAMLError:
        logger.exception("Couldn't load config from YAML file: %s", config_file)
    else:
        return config


def s3_resource(config):
    # TODO: check if this works with other type
    resource = boto3.resource(
        's3',
        region_name=config['aws_general']['region_name'],
        verify=config['aws_general']['verify'],
        config=Config(signature_version='s3v4')
    )
    return resource


def download_from_s3(config, resource, object_key):
    file_obj = BytesIO()
    client = resource.meta.client
    try:
        client.download_fileobj(config['s3']['bucket'], object_key, file_obj)
    except ClientError as cli_err:
        logger.error("Boto ClientError downloading from S3: %s", cli_err)
    else:
        return file_obj


def epoch_time():
    return int(time.time())


def connect_to_aws_resource(resource_name, config):
    try:
        resource = boto3.resource(
            resource_name, region_name=config['aws_general']['region_name'], verify=True)
    except SSLError as ssl_err:
        logger.info("SSL Error: %s", ssl_err, exc_info=True)
    else:
        return resource


def get_item_by_partition_and_sort_key(task, resource, table_name, partition_key, sort_key):
    """
    Get a response object from DynamoDB by forming a compound key of the partition and sort key.
    :param task: Dictionary of task details
    :param table_name: String of DynamoDB table name
    :param partition_key: String of partition key name
    :param sort_key: String of sort key name
    :return: Dictionary of response from DynamoDB
    """
    table = resource.Table(table_name)
    return table.query(
        KeyConditionExpression='#pk = :{} AND #sk = :{}'.format(partition_key, sort_key),
        ExpressionAttributeNames={
            '#pk': '{}'.format(partition_key),
            '#sk': '{}'.format(sort_key)
        },
        ExpressionAttributeValues={
            ':{}'.format(partition_key): task['{}'.format(partition_key)],
            ':{}'.format(sort_key): task['{}'.format(sort_key)]
        }
    )


def get_item_by_composite_key(resource, table_name, key_names, key_values):
    table = resource.Table(table_name)
    response = table.get_item(
        Key={
            '{}'.format(key_names.get('first')): key_values.get('first'),
            '{}'.format(key_names.get('second')): key_values.get('second'),
        }
    )
    return response['Item']


def get_items_by_partition_key(resource, table_name, key_name, key_value):
    table = resource.Table(table_name)
    response = table.query(KeyConditionExpression=Key(key_name).eq(key_value))
    return response['Items']


def get_item_by_partition_key_and_sort_key():
    pass


def put_item_with_partition_and_sort_key(resource, table_name, partition_and_sort_key, data):
    table = resource.Table(table_name)
    item = {
        partition_and_sort_key['partition_key_name']: partition_and_sort_key['partition_key_value'],
        partition_and_sort_key['sort_key_name']: partition_and_sort_key['sort_key_value']
    }
    item.update(data)
    table.put_item(Item=item)


def update_item_by_partition_and_sort_key(resource, table_name, task):
    table = resource.Table(table_name)
    table.update_item(
        Key={
            '{}'.format(task['partition_key_name']): '{}'.format(task['partition_key_value']),
            '{}'.format(task['sort_key_name']): '{}'.format(task['sort_key_value'])
        },
        UpdateExpression='SET {} = :value'.format(task.get('test_type')),
        ExpressionAttributeValues={
            ':value': task.get('test_result')
        }
    )


def get_s3_resource(config):
    """
    Creates boto resource object for S3 and returns

    :param config: Global config dictionary
    :return: boto s3 resource
    """
    return boto3.resource(
        's3',
        region_name=config['s3']['region_name'],
        verify=config['s3']['verify'],
        config=Config(signature_version='s3v4')
    )


def get_s3_client(config):
    """
    Creates boto clientobject for S3 and returns

    :param config: Global config dictionary
    :return: boto s3 client
    """
    return boto3.client(
        's3',
        region_name=config['s3']['region_name'],
        verify=config['s3']['verify'],
        config=Config(signature_version='s3v4')
    )


def get_boto_client(service):
    return boto3.client(service)


def get_certs():
    pool_manager = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
    return pool_manager.connection_pool_kw.get('ca_certs')
