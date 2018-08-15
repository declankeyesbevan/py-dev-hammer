"""
Utilities for interacting with AWS.
"""

# pylint: disable=logging-fstring-interpolation, invalid-name, missing-docstring

import logging

import boto3
from boto3.dynamodb.conditions import Key
from botocore.vendored.requests.exceptions import SSLError

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())


def connect_to_aws_resource(resource_name, config):
    try:
        resource = boto3.resource(
            resource_name, region_name=config['aws_general']['region_name'], verify=True)
    except SSLError as ssl_err:
        logger.error(f"SSL Error: {ssl_err}", exc_info=True)
    else:
        return resource


def get_boto_client(service):
    return boto3.client(service)


def get_items_by_partition_key(resource, table_name, key_name, key_value):
    table = resource.Table(table_name)
    response = table.query(KeyConditionExpression=Key(key_name).eq(key_value))
    return response['Items']


def put_with_partition_and_sort_key(resource, table_name, partition_and_sort_key, data):
    table = resource.Table(table_name)
    item = {
        partition_and_sort_key['partition_key_name']: partition_and_sort_key['partition_key_value'],
        partition_and_sort_key['sort_key_name']: partition_and_sort_key['sort_key_value']
    }
    item.update(data)
    table.put_item(Item=item)
