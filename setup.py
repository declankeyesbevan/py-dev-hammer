"""
Sets up PyDevHammer so you can Hammer your Py Dev.
"""
# pylint: disable=redefined-builtin

from codecs import open
from os import path
from setuptools import setup, find_packages

HERE = path.abspath(path.dirname(__file__))
with open(path.join(HERE, 'README.md'), encoding='utf-8') as readme_file:
    README = readme_file.read()
with open(path.join(HERE, 'HISTORY.md'), encoding='utf-8') as history_file:
    HISTORY = history_file.read().replace('.. :changelog:', '')

ROOT_URL = 'https://github.com/declankeyesbevan/py-dev-hammer'

setup(
    name='pydevhammer',
    use_scm_version=True,
    description='Python development tools using AWS and GitHub',
    long_description=f'{README}\n{HISTORY}',
    long_description_content_type='text/markdown',
    url=ROOT_URL,
    author='Declan Keyes-Bevan',
    author_email='declankeyesbevan@users.noreply.github.com',
    license='MIT',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.6',
    ],
    keywords='github aws codebuild continuous-integration dev-tools',
    packages=find_packages(exclude=['tests']),
    install_requires=[
        'boto3',
        'botocore',
        'certifi',
        'coverage',
        'dpath',
        'linecounter',
        'pylint',
        'pytest',
        'PyYAML',
        'requests',
        'urllib3',
    ],
    setup_requires=[
        'setuptools_scm',
    ],
    python_requires='~=3.6',
    entry_points={
        'console_scripts': [
            'github_status_posting=py_dev_hammer.github_status_posting:entry_point',
        ]
    },
    project_urls={
        'Documentation': f'{ROOT_URL}/docs',
        'Issues': f'{ROOT_URL}/issues',
        'Source': ROOT_URL,
    },
)
