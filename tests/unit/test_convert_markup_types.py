"""This unit tests convert_markup_types."""

# pylint: disable=missing-docstring, no-self-use, invalid-name

import os
import shutil

from unittest.mock import patch

import pytest

from py_dev_hammer.convert_markup_types import entry_point, _execute
from tests import TEST_RESOURCES_DIR
from tests.data_factory import USER_CONFIG, PARSER
from utils.errors import GeneralError

MODULE_UNDER_TEST = 'py_dev_hammer.convert_markup_types'


class TestConvertMarkupTypes(object):

    @patch('{}._execute'.format(MODULE_UNDER_TEST))
    @patch('logging.Logger.error')
    def test_entry_point(self, mock_logger, mock_execute):
        args = PARSER.parse_args(['--config', os.path.join(TEST_RESOURCES_DIR, 'user_config.yml')])
        entry_point(args)
        assert mock_execute.called

        mock_execute.side_effect = GeneralError()
        entry_point(args)
        assert "GeneralError in Convert Markup Types" in str(mock_logger.mock_calls)

    def test_execute(self):
        project_directory = os.environ['PROJECT_DIR']
        build_directory = os.path.join(project_directory, 'build', 'docs')
        if os.path.exists(build_directory):
            shutil.rmtree(build_directory)

        file_names = [file_name.lower() for file_name in USER_CONFIG['markdown']['files']]
        _execute(file_names)
        file_format = 'rst'
        for file_name in file_names:
            file_name_and_extension = '{}.{}'.format(file_name, file_format)
            sample = os.path.join(build_directory, file_name_and_extension)
            build = os.path.join(project_directory, file_name_and_extension)
            sample_open = open(sample).readlines()
            build_open = open(build).readlines()
            for index, _ in enumerate(sample_open):
                assert sample_open[0] == build_open[0]

        with patch('{}.convert_file'.format(MODULE_UNDER_TEST)) as mock_convert_file:
            mock_convert_file.side_effect = RuntimeError
            with pytest.raises(GeneralError):
                _execute(file_names)
