"""This is for converting Markdown files to reStructuredText files."""

import os

from pypandoc import convert_file

from utils.errors import GeneralError
from utils.utils import logger, load_config_file

# TODO: move to either user or app config
APP_CONFIG = load_config_file('app_config.yml')


def entry_point(args):
    logger.info("Starting at entry point.")

    user_config = load_config_file(args.config)
    file_names = [file_name.lower() for file_name in user_config['markdown']['files']]

    try:
        _execute(file_names)
    except GeneralError as gen_err:
        logger.error("GeneralError in Convert Markup Types: %s", gen_err, exc_info=True)
    else:
        logger.info("Successfully executed Convert Markup Types.")


def _execute(file_names):

    logger.info("Starting conversion of root Markdown files to reStructuredText.")

    build_directory = os.path.join(os.environ['PROJECT_DIR'], 'build', 'docs')
    if not os.path.exists(build_directory):
        os.makedirs(build_directory)

    file_format = 'rst'
    try:
        for file_name in file_names:
            convert_file(
                os.path.join(os.environ['PROJECT_DIR'], '{}.{}'.format(file_name, 'md')),
                file_format,
                outputfile=os.path.join(build_directory, '{}.{}'.format(file_name, file_format))
            )
    except RuntimeError as rnt_err:
        raise GeneralError("RuntimeError: {}".format(rnt_err))
    else:
        logger.info("File(s) converted.")
