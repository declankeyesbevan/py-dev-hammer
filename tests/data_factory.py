"""This provides a common set of test data for unit, integration and functional tests."""

import argparse
import decimal
import os

from tests import TEST_RESOURCES_DIR
from utils.general import load_config_file

APP_CONFIG = load_config_file(os.path.join(TEST_RESOURCES_DIR, 'app_config_test.yml'))
USER_CONFIG = load_config_file(os.path.join(TEST_RESOURCES_DIR, 'user_config_test.yml'))
REGION = 'ap-southeast-2'
GITHUB_TOKEN = '297045966567'
PROJECT_NAME = 'some-cool-name'
BUILD_ID = '4d8d41b2-ed71-94ed-cc25-161f829f1e7a'
CODEBUILD_BUILD_ARN = (
    'arn:aws:codebuild:{}:{}:build/{}:{}'.format(REGION, GITHUB_TOKEN, PROJECT_NAME, BUILD_ID))
CODE_BUILD_BUILD_URL = (
    'https://{region}.console.aws.amazon.com/codebuild/home?region={region}#/'
    'builds/{project_name}:{build_id}/view/new'.format(
        region=REGION, project_name=PROJECT_NAME, build_id=BUILD_ID)
)
CODEBUILD_GIT_BRANCH = 'COOL-NAME-8-unit-tests'
CODEBUILD_SOURCE_VERSION = '41db5ed82c0f19ab460efeb30ec116e2bf3a210b'
TEST_PARAM_DICT_PYTEST_PASS = {
    'test_type': 'pytest',
    'input_file': os.path.join(TEST_RESOURCES_DIR, 'pytest_pass.xml'),
    'regex_pattern': r'.*(errors="\d") (failures="\d").*(skips="\d").*(tests="\d")',
    'message': 'Pytest score',
    'multiplier': 100,
    'percent': True,
}
TEST_PARAM_DICT_PYTEST_FAIL = {
    'test_type': 'pytest',
    'input_file': os.path.join(TEST_RESOURCES_DIR, 'pytest_fail.xml'),
    'regex_pattern': r'.*(errors="\d") (failures="\d").*(skips="\d").*(tests="\d")',
    'message': 'Pytest score',
    'multiplier': 100,
    'percent': True,
}
TEST_PARAM_DICT_PYLINT = {
    'test_type': 'pylint',
    'input_file': os.path.join(TEST_RESOURCES_DIR, 'pylint.static'),
    'regex_pattern': '.*?(\\d+.\\d+)/10$',
    'message': 'Pylint score',
    'multiplier': 10,
    'percent': True,
}
TEST_PARAM_DICT_MISSING_FILE = {
    'test_type': 'pytest',
    'input_file': 'canny_find_it_captain',
    'regex_pattern': r'.*(errors="\d") (failures="\d").*(skips="\d").*(tests="\d")',
    'message': 'Pytest score',
    'multiplier': 100,
    'percent': True,
}
GITHUB_PAYLOAD = {
    'state': 'success',
    'target_url': CODE_BUILD_BUILD_URL,
    'description': 'Pylint score: 100%, Change from previous: -10',
    'context': 'pylint'
}
DYNAMO_PAYLOAD = {
    'pylint': decimal.Decimal('100.0'),
}
BUILD_START_TIME_FIRST_RUN = 1520333673
BUILD_START_TIME_SECOND_RUN = 1520334089
DYNAMO_ITEMS = [
    {
        'branch_name': CODEBUILD_GIT_BRANCH,
        'build_start_time': decimal.Decimal('{}'.format(BUILD_START_TIME_FIRST_RUN)),
        'pylint': decimal.Decimal('100')
    },
    {
        'branch_name': CODEBUILD_GIT_BRANCH,
        'build_start_time': decimal.Decimal('{}'.format(BUILD_START_TIME_SECOND_RUN)),
        'pylint': decimal.Decimal('90')
    }
]
