"""This unit tests github_status_posting."""

# pylint: disable=missing-docstring, no-self-use, invalid-name

import os
from unittest.mock import patch, MagicMock

import pytest
from requests.exceptions import MissingSchema

from py_dev_hammer.github_status_posting import (
    entry_point, _execute, _parse_url_from_arn, _create_test_parameters_dict,
    _update_dynamo_payload, _maintain_state_in_dynamo, _create_github_payloads,
    _get_change_from_previous, _parse_pytest, _parse_quality_indicator_tests,
    _post_to_github_status,
)
from tests import TEST_RESOURCES_DIR
from tests.data_factory import (
    APP_CONFIG, USER_CONFIG, CODEBUILD_BUILD_ARN, CODE_BUILD_BUILD_URL, CODEBUILD_GIT_BRANCH,
    CODEBUILD_SOURCE_VERSION, TEST_PARAM_DICT_PYTEST_PASS, TEST_PARAM_DICT_PYTEST_FAIL,
    TEST_PARAM_DICT_PYLINT, TEST_PARAM_DICT_MISSING_FILE, GITHUB_PAYLOAD, DYNAMO_PAYLOAD,
    BUILD_START_TIME_FIRST_RUN, DYNAMO_ITEMS,
)
from py_dev_hammer.utils.errors import GeneralError
from py_dev_hammer.utils.general import get_certs

MODULE_UNDER_TEST = 'py_dev_hammer.github_status_posting'


class TestGithubStatusPosting(object):

    @patch('{}.APP_CONFIG'.format(MODULE_UNDER_TEST), APP_CONFIG)
    @patch('{}.USER_CONFIG'.format(MODULE_UNDER_TEST), USER_CONFIG)
    @patch('{}._create_test_parameters_dict'.format(MODULE_UNDER_TEST))
    @patch(
        '{}._parse_url_from_arn'.format(MODULE_UNDER_TEST),
        new=MagicMock(return_value=CODE_BUILD_BUILD_URL)
    )
    @patch('{}._execute'.format(MODULE_UNDER_TEST))
    @patch('logging.Logger.error')
    def test_entry_point(self, mock_logger, mock_execute, mock_parameters_dict):
        entry_point()
        assert mock_parameters_dict.called
        assert os.environ['REQUESTS_CA_BUNDLE'] == get_certs()
        assert mock_execute.called

        mock_execute.side_effect = GeneralError()
        entry_point()
        assert "GeneralError in GitHub Status Posting" in str(mock_logger.mock_calls)

    @patch('{}._parse_pytest'.format(MODULE_UNDER_TEST), new=MagicMock(return_value=('success', 1)))
    @patch(
        '{}._update_dynamo_payload'.format(MODULE_UNDER_TEST),
        new=MagicMock(return_value=DYNAMO_PAYLOAD)
    )
    @patch(
        '{}._parse_quality_indicator_tests'.format(MODULE_UNDER_TEST),
        new=MagicMock(return_value=10.0)
    )
    @patch(
        '{}._maintain_state_in_dynamo'.format(MODULE_UNDER_TEST),
        new=MagicMock(return_value=DYNAMO_ITEMS)
    )
    @patch(
        '{}._create_github_payloads'.format(MODULE_UNDER_TEST),
        new=MagicMock(return_value=[GITHUB_PAYLOAD])
    )
    @patch('{}._post_to_github_status'.format(MODULE_UNDER_TEST))
    @pytest.mark.parametrize('param_dict, url', [
        (TEST_PARAM_DICT_PYTEST_PASS, CODE_BUILD_BUILD_URL),
        (TEST_PARAM_DICT_PYLINT, CODE_BUILD_BUILD_URL),
    ])
    def test_execute(self, mock_github, param_dict, url):
        _execute(
            USER_CONFIG, [param_dict], url, APP_CONFIG['tests_to_run']['dynamic'],
            APP_CONFIG['tests_to_run']['static']
        )
        assert mock_github.called

    @patch('{}.APP_CONFIG'.format(MODULE_UNDER_TEST), APP_CONFIG)
    @patch.dict(os.environ, {'CODEBUILD_BUILD_ARN': CODEBUILD_BUILD_ARN})
    def test_parse_url_from_arn(self):
        assert _parse_url_from_arn(USER_CONFIG) == CODE_BUILD_BUILD_URL

    @patch('{}.APP_CONFIG'.format(MODULE_UNDER_TEST), APP_CONFIG)
    def test_create_test_parameters_dict(self):
        for key, value in _create_test_parameters_dict('pylint', TEST_RESOURCES_DIR).items():
            assert TEST_PARAM_DICT_PYLINT.get(key) == value

    def test_update_dynamo_payload(self):
        assert _update_dynamo_payload(TEST_PARAM_DICT_PYLINT, 10.0, {}) == DYNAMO_PAYLOAD

    @patch.dict(os.environ, {'CODEBUILD_GIT_BRANCH': CODEBUILD_GIT_BRANCH})
    @patch('{}.connect_to_aws_resource'.format(MODULE_UNDER_TEST), new=MagicMock())
    @patch('{}.APP_CONFIG'.format(MODULE_UNDER_TEST), APP_CONFIG)
    @patch('{}.put_with_partition_and_sort_key'.format(MODULE_UNDER_TEST), new=MagicMock())
    @patch('{}.get_items_by_partition_key'.format(MODULE_UNDER_TEST))
    def test_maintain_state_in_dynamo(self, mock_items_partition_key):
        _maintain_state_in_dynamo(USER_CONFIG, BUILD_START_TIME_FIRST_RUN, DYNAMO_PAYLOAD)
        assert mock_items_partition_key.called

    @patch('{}.APP_CONFIG'.format(MODULE_UNDER_TEST), APP_CONFIG)
    @patch(
        '{}._get_change_from_previous'.format(MODULE_UNDER_TEST), new=MagicMock(return_value=-10))
    def test_create_github_payloads(self):
        assert _create_github_payloads(
            'success', CODE_BUILD_BUILD_URL, DYNAMO_PAYLOAD, DYNAMO_ITEMS) == [GITHUB_PAYLOAD]

    def test_get_change_from_previous(self):
        assert _get_change_from_previous('pylint', DYNAMO_ITEMS) == -10

    @pytest.mark.parametrize('param_dict, state, score', [
        (TEST_PARAM_DICT_PYTEST_PASS, 'success', 1),
        (TEST_PARAM_DICT_PYTEST_FAIL, 'failure', 0.875),
    ])
    def test_parse_pytest(self, param_dict, state, score):
        assert _parse_pytest(param_dict) == (state, score)
        with pytest.raises(GeneralError):
            _parse_pytest(TEST_PARAM_DICT_MISSING_FILE)

    def test_parse_quality_indicator_tests(self):
        assert _parse_quality_indicator_tests(TEST_PARAM_DICT_PYLINT) == 10.0
        with pytest.raises(GeneralError):
            _parse_quality_indicator_tests(TEST_PARAM_DICT_MISSING_FILE)

    @patch.dict(os.environ, {'CODEBUILD_SOURCE_VERSION': CODEBUILD_SOURCE_VERSION})
    @patch('{}.get_boto_client'.format(MODULE_UNDER_TEST), new=MagicMock())
    @patch('{}.APP_CONFIG'.format(MODULE_UNDER_TEST), APP_CONFIG)
    @patch('{}.requests.post'.format(MODULE_UNDER_TEST))
    def test_post_to_github_status(self, mock_requests):
        _post_to_github_status(GITHUB_PAYLOAD, USER_CONFIG)
        assert mock_requests.called

        mock_requests.side_effect = MissingSchema
        with pytest.raises(GeneralError):
            _post_to_github_status(GITHUB_PAYLOAD, USER_CONFIG)
