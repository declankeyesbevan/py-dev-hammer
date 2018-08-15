#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This carries out dynamic and static code analysis and POSTs the results to GitHub as statuses.
Without passing statuses, a pull request cannot be merged. Dynamic tests require 100% passing to be
considered a success. The static tests are informational only and will always generate success if
they run correctly.
"""

# pylint: disable=logging-fstring-interpolation

import decimal
import json
import os
import re
import time

import dpath
import requests
from requests.exceptions import MissingSchema

from py_dev_hammer.utils.aws import (
    connect_to_aws_resource, get_items_by_partition_key, put_with_partition_and_sort_key,
    get_boto_client,
)
from py_dev_hammer.utils.errors import GeneralError
from py_dev_hammer.utils.general import logger, load_config_file, get_certs

APP_CONFIG = load_config_file(f"{os.environ.get('CONFIG_DIR')}/app_config.yml")
USER_CONFIG = load_config_file(f"{os.environ.get('CONFIG_DIR')}/user_config.yml")


def entry_point():
    """
    Allows the module to be called from the command line.
    """
    logger.info("Starting at entry point")

    dynamic_test_types = list(APP_CONFIG['tests_to_run']['dynamic'].keys())
    static_test_types = list(APP_CONFIG['tests_to_run']['static'].keys())
    test_types = dynamic_test_types + static_test_types

    static_results_dir = os.path.join(
        APP_CONFIG['static_analysis']['root_dir'], APP_CONFIG['static_analysis']['results_dir'])
    test_parameters = [
        _create_test_parameters_dict(test_type, static_results_dir) for test_type in test_types]
    target_url = _parse_url_from_arn(USER_CONFIG)
    os.environ['REQUESTS_CA_BUNDLE'] = get_certs()

    try:
        _execute(USER_CONFIG, test_parameters, target_url, dynamic_test_types, static_test_types)
    except GeneralError as gen_err:
        logger.error(f"GeneralError in GitHub Status Posting: {gen_err}", exc_info=True)
    else:
        logger.info("Successfully executed GitHub Status Posting")


def _execute(user_config, test_parameters, target_url, dynamic_test_types, static_test_types):
    logger.info("Executing main function")

    pytest_state = 'failure'
    dynamo_payload = {}
    for test_parameter in test_parameters:
        if test_parameter.get('test_type') in dynamic_test_types:
            pytest_state, score = _parse_pytest(test_parameter)
            dynamo_payload = _update_dynamo_payload(test_parameter, score, dynamo_payload)
        elif test_parameter.get('test_type') in static_test_types:
            score = _parse_quality_indicator_tests(test_parameter)
            dynamo_payload = _update_dynamo_payload(test_parameter, score, dynamo_payload)

    build_start_time = int(time.time())
    dynamo_items = _maintain_state_in_dynamo(user_config, build_start_time, dynamo_payload)

    github_payloads = _create_github_payloads(
        pytest_state, target_url, dynamo_payload, dynamo_items)
    for github_payload in github_payloads:
        _post_to_github_status(github_payload, user_config)


def _parse_url_from_arn(user_config):
    logger.info(f"Parsing URL from ARN: {os.environ['CODEBUILD_BUILD_ARN']}")

    line_regex = re.compile(r'.*/.*:(.+)')
    line_parse = re.match(line_regex, os.environ['CODEBUILD_BUILD_ARN'])
    return APP_CONFIG['code_build']['root_url'].format(
        region=user_config['aws_general']['region_name'],
        project_name=user_config['code_build']['project_name'],
        build_id=line_parse.group(1)
    )


def _create_test_parameters_dict(test_type, static_results_dir):
    logger.info(f"Creating test parameters dict: {test_type}")

    test_to_run = dpath.get(APP_CONFIG['tests_to_run'], f'*/{test_type}')

    return {
        'test_type': test_type,
        'input_file': os.path.join(static_results_dir, test_to_run['input_file']),
        'regex_pattern': fr"{test_to_run['regex_pattern']}",
        'message': test_to_run['message'],
        'multiplier': test_to_run['multiplier'],
        'percent': test_to_run['percent']
    }


def _update_dynamo_payload(test_parameter, score, dynamo_payload):
    logger.info(f"Updating DynamoDB payload: {test_parameter.get('test_type')}")

    dynamo_payload.update({
        test_parameter.get('test_type'):
            decimal.Decimal(f"{score * test_parameter.get('multiplier')}")
    })
    return dynamo_payload


def _maintain_state_in_dynamo(user_config, build_start_time, dynamo_payload):
    logger.info("Maintaining state in DynamoDB")

    branch_parse = re.match(
        re.compile(r'(remotes/origin/)*(.+)'), os.environ['CODEBUILD_GIT_BRANCH'])
    branch_name = branch_parse.group(2)

    resource = connect_to_aws_resource('dynamodb', user_config)

    partition_key_name = APP_CONFIG['dynamo']['partition_key_name']
    table_name = APP_CONFIG['dynamo']['table_name']
    sort_key_name = APP_CONFIG['dynamo']['sort_key_name']

    partition_and_sort_key = {
        'partition_key_name': partition_key_name,
        'partition_key_value': branch_name,
        'sort_key_name': sort_key_name,
        'sort_key_value': build_start_time,
    }

    put_with_partition_and_sort_key(
        resource, table_name, partition_and_sort_key, dynamo_payload)
    return get_items_by_partition_key(resource, table_name, partition_key_name, branch_name)


def _create_github_payloads(pytest_state, target_url, dynamo_payload, dynamo_items):
    logger.info("Creating GitHub payloads")

    github_payloads = []
    for test_type, test_value in dynamo_payload.items():
        test_to_run = dpath.get(APP_CONFIG['tests_to_run'], f'*/{test_type}')
        description = '{message}: {multiplier:.0f}{percent}, Change from previous: {change}'.format(
            message=test_to_run.get('message'),
            multiplier=test_value,
            percent='%' if test_to_run.get('percent') else '',
            change=_get_change_from_previous(test_type, dynamo_items)
        )
        github_payload = {
            'state': pytest_state if test_type in 'pytest' else 'success',
            'target_url': target_url,
            'description': description,
            'context': test_type,
        }
        github_payloads.append(github_payload)
    return github_payloads


def _get_change_from_previous(test_type, dynamo_items):
    logger.info(f"Getting change from previous build: {test_type}")

    change_value = 'N/A - first build'
    if len(dynamo_items) > 1:
        change_value = dynamo_items[-1].get(test_type) - dynamo_items[-2].get(test_type)
    return change_value


def _parse_pytest(test_parameter):
    logger.info("Parsing PyTest")

    try:
        file = open(test_parameter.get('input_file'), 'r')
    except FileNotFoundError as fil_err:
        raise GeneralError(f"File not found error: {fil_err}")
    else:
        line_parse = re.match(
            re.compile(fr"{test_parameter.get('regex_pattern')}"), file.readlines()[0])
        test_range = 5
        results_to_parse = [line_parse.group(iterator) for iterator in range(1, test_range)]

        results = {
            res.split(sep='=')[0]: int(res.split(sep='=')[1].strip('"')) for res in results_to_parse
        }
        state = (
            'failure' if results.get('errors') is not 0 or
            results.get('failures') is not 0 else 'success'
        )

        total_problems = results.get('errors') + results.get('failures')
        total_tests = results.get('tests')
        score = 1
        if total_problems is not 0:
            score = (total_tests - total_problems) / total_tests
        return state, score


def _parse_quality_indicator_tests(test_parameter):
    logger.info(f"Parsing quality indicator tests: {test_parameter.get('test_type')}")

    try:
        file = open(test_parameter.get('input_file'), 'r')
    except FileNotFoundError as fil_err:
        raise GeneralError(f"File not found error: {fil_err}")
    else:
        score = 100.0
        for line in file.readlines():
            line_parse = re.match(
                re.compile(fr"{test_parameter.get('regex_pattern')}"), line.strip('\n'))
            if line_parse is not None:
                score = float(line_parse.group(1))
        return score


def _post_to_github_status(data, user_config):
    logger.info(f"Starting POST to GitHub: {data.get('context')}")

    ssm_parameters = {}
    for param in ['github_owner', 'github_token']:
        this_param = get_boto_client('ssm').get_parameter(Name=param, WithDecryption=True)
        ssm_parameters.update({
            this_param.get('Parameter').get('Name'): this_param.get('Parameter').get('Value')})
    url = APP_CONFIG['github']['api_url'].format(
        owner=ssm_parameters.get('github_owner'),
        repo=user_config['github']['repo'],
        commit_sha=os.environ['CODEBUILD_SOURCE_VERSION']
    )
    headers = {"Authorization": f"token {ssm_parameters.get('github_token')}"}

    try:
        response = requests.post(url, data=json.dumps(data), headers=headers, verify=True)
    except MissingSchema as sch_exc:  # If URL is incorrect, other errors are HTTP codes
        raise GeneralError(f"POST to GitHub MissingSchema Exception: {sch_exc}")
    else:
        logger.info(f"POST Response Code: {response.status_code}")


if __name__ == '__main__':
    entry_point()
