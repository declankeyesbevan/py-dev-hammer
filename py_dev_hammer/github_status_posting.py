"""This carries out static code analysis and POSTs the results to GitHub as statuses. Without
passing statuses, a pull request cannot be merged. Unit tests require 100% passing to be considered
a success. The other packages are informational only and will always generate success if they run
correctly."""

import decimal
import json
import os
import re

import requests
from requests.exceptions import MissingSchema

from utils.errors import GeneralError
from utils.utils import (
    logger, load_config_file, epoch_time, get_items_by_partition_key,
    put_item_with_partition_and_sort_key, connect_to_aws_resource, get_boto_client, get_certs,
)

# TODO: move to either user or app config
APP_CONFIG = load_config_file('app_config.yml')
PYTEST_TYPES = ['pytest']
QUALITY_INDICATOR_TEST_TYPES = ['pylint', 'coverage', 'radon_cc', 'line_counter']
TEST_TYPES = PYTEST_TYPES + QUALITY_INDICATOR_TEST_TYPES
TABLE_NAME = 'build-status'
PARTITION_KEY_NAME = 'branch_name'
SORT_KEY_NAME = 'build_start_time'


def entry_point(args):
    """
    Pass in the command line arguments to begin processing.

    :param args: Command line arguments
    :type args: :class: `argparse.Namespace`
    """
    logger.info("Starting at entry point.")

    user_config = load_config_file(args.config)
    test_log_dir = os.path.join(APP_CONFIG['tests']['root_dir'], APP_CONFIG['tests']['logs_dir'])
    test_parameters = [
        _create_test_parameters_dict(test_type, test_log_dir) for test_type in TEST_TYPES]
    target_url = _parse_url_from_arn(user_config)
    os.environ['REQUESTS_CA_BUNDLE'] = get_certs()

    try:
        _execute(user_config, test_parameters, target_url)
    except GeneralError as gen_err:
        logger.error("GeneralError in GitHub Status Posting: %s", gen_err, exc_info=True)
    else:
        logger.info("Successfully executed GitHub Status Posting.")


def _execute(user_config, test_parameters, target_url):
    logger.info("Executing main function.")

    pytest_state = 'failure'
    dynamo_payload = {}
    for test_parameter in test_parameters:
        if test_parameter.get('test_type') in PYTEST_TYPES:
            pytest_state, score = _parse_pytest(test_parameter)
            dynamo_payload = _update_dynamo_payload(test_parameter, score, dynamo_payload)
        elif test_parameter.get('test_type') in QUALITY_INDICATOR_TEST_TYPES:
            score = _parse_quality_indicator_tests(test_parameter)
            dynamo_payload = _update_dynamo_payload(test_parameter, score, dynamo_payload)

    build_start_time = epoch_time()
    dynamo_items = _maintain_state_in_dynamo(user_config, build_start_time, dynamo_payload)

    github_payloads = _create_github_payloads(
        pytest_state, target_url, dynamo_payload, dynamo_items)
    for github_payload in github_payloads:
        _post_to_github_status(github_payload, user_config)


def _parse_url_from_arn(user_config):
    logger.info("Parsing URL from ARN.")

    line_regex = re.compile(r'.*/.*:(.+)')
    line_parse = re.match(line_regex, os.environ['CODEBUILD_BUILD_ARN'])
    return APP_CONFIG['code_build']['root_url'].format(
        region=user_config['aws_general']['region_name'],
        project_name=user_config['code_build']['project_name'],
        build_id=line_parse.group(1)
    )


def _create_test_parameters_dict(test_type, test_log_dir):
    logger.info("Creating test parameters dict: %s.", test_type)

    return {
        'test_type': test_type,
        'input_file': os.path.join(test_log_dir, APP_CONFIG[test_type]['input_file']),
        'regex_pattern': r'{}'.format(APP_CONFIG[test_type]['regex_pattern']),
        'message': APP_CONFIG[test_type]['message'],
        'multiplier': APP_CONFIG[test_type]['multiplier'],
        'percent': APP_CONFIG[test_type]['percent']
    }


def _update_dynamo_payload(test_parameter, score, dynamo_payload):
    logger.info("Updating DynamoDB payload: %s.", test_parameter.get('test_type'))

    dynamo_payload.update(
        {
            test_parameter.get('test_type'):
                decimal.Decimal('{}'.format(score * test_parameter.get('multiplier')))
        }
    )
    return dynamo_payload


def _maintain_state_in_dynamo(user_config, build_start_time, dynamo_payload):
    logger.info("Maintaining state in DynamoDB.")

    branch_regex = re.compile(r'(remotes/origin/)*(.+)')
    branch_parse = re.match(branch_regex, os.environ['CODEBUILD_GIT_BRANCH'])
    branch_name = branch_parse.group(2)
    resource = connect_to_aws_resource('dynamodb', user_config)
    partition_and_sort_key = {
        'partition_key_name': PARTITION_KEY_NAME,
        'partition_key_value': branch_name,
        'sort_key_name': SORT_KEY_NAME,
        'sort_key_value': build_start_time,
    }
    put_item_with_partition_and_sort_key(
        resource, TABLE_NAME, partition_and_sort_key, dynamo_payload)
    return get_items_by_partition_key(resource, TABLE_NAME, PARTITION_KEY_NAME, branch_name)


def _create_github_payloads(pytest_state, target_url, dynamo_payload, dynamo_items):
    logger.info("Creating GitHub payloads.")

    github_payloads = []
    for test_type, test_value in dynamo_payload.items():
        description = '{message}: {multiplier:.0f}{percent}, Change from previous: {change}'.format(
            message=APP_CONFIG.get(test_type).get('message'),
            multiplier=test_value,
            percent='%' if APP_CONFIG.get(test_type).get('percent') else '',
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
    logger.info("Getting change from previous build: %s.", test_type)

    change_value = 'N/A - first build'
    if len(dynamo_items) > 1:
        change_value = dynamo_items[-1].get(test_type) - dynamo_items[-2].get(test_type)
    return change_value


def _parse_pytest(test_parameter):
    logger.info("Parsing PyTest.")

    try:
        file = open(test_parameter.get('input_file'), 'r')
    except FileNotFoundError as fil_err:
        raise GeneralError("File not found error: {}".format(fil_err))
    else:
        lines = file.readlines()
        line_regex = re.compile(r'{}'.format(test_parameter.get('regex_pattern')))
        line_parse = re.match(line_regex, lines[0])
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
    logger.info("Parsing quality indicator tests: %s.", test_parameter.get('test_type'))

    try:
        file = open(test_parameter.get('input_file'), 'r')
    except FileNotFoundError as fil_err:
        raise GeneralError("File not found error: {}.".format(fil_err))
    else:
        lines = file.readlines()
        line_regex = re.compile(r'{}'.format(test_parameter.get('regex_pattern')))
        score = 100.0
        for line in lines:
            line_parse = re.match(line_regex, line.strip('\n'))
            if line_parse is not None:
                score = float(line_parse.group(1))
        return score


def _post_to_github_status(data, user_config):
    logger.info("Starting POST to GitHub: %s.", data.get('context'))

    commit_sha = os.environ['CODEBUILD_SOURCE_VERSION']
    client = get_boto_client('ssm')
    github_encrypted_parameters = ['github_owner', 'github_token']
    ssm_parameters = {}
    for param in github_encrypted_parameters:
        this_param = client.get_parameter(Name=param, WithDecryption=True)
        ssm_parameters.update({
            this_param.get('Parameter').get('Name'): this_param.get('Parameter').get('Value')})
    api_url = APP_CONFIG['github']['api_url']
    url = api_url.format(
        owner=ssm_parameters.get('github_owner'),
        repo=user_config['github']['repo'],
        commit_sha=commit_sha
    )
    headers = {'Authorization': 'token {}'.format(ssm_parameters.get('github_token'))}

    try:
        response = requests.post(url, data=json.dumps(data), headers=headers, verify=True)
    except MissingSchema as sch_exc:  # If URL is incorrect, other errors are HTTP codes
        raise GeneralError("POST to GitHub MissingSchema Exception: {}.".format(sch_exc))
    else:
        logger.info("POST Response Code: %s.", response.status_code)
