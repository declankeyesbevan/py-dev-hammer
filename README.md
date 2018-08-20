# Py Dev Hammer

:snake: :nerd_face: :hammer:  
When all you have is a hammer, everything looks like a dev.

## About

Py Dev Hammer is a collection of tools to help in developing Python applications. 

This pre-alpha release contains a single tool. It is a Continuous Integration helper which performs
dynamic and static code analysis on your project and POSTs the results to GitHub as statuses.

See [road map](#road-map) for further release plans. The first item is to use AWS CloudFormation to
make most of this document redundant. As the project progresses this README will reference other
READMEs instead of detailing everything.

## Installation
`pip install pydevhammer`

## Pre-requisites
Note: this guide attempts to keep specific references to third-party tools to a minimum as they are
very likely to change. Use your intuition and please get in
[contact](https://www.declankeyesbevan.com/contact) if there are glaring problems and/or you want to
buy me a beer. The latter is recommended.

### GitHub
To enable Continuous Integration of your commits, GitHub communicates with AWS CodeBuild via
[Webhooks](https://help.github.com/articles/about-webhooks/). For ease of use you can set this up in
the [GitHub UI](https://developer.github.com/webhooks/creating/#setting-up-a-webhook) rather than
using the API. The following options should be used:

- Payload URL: `https://codebuild.{your-aws-region}.amazonaws.com/webhooks`
- Content type: `application/json`
- Secret: [Create a secure secret](https://developer.github.com/webhooks/securing/)
- SSL verification: `Enable`
- Which events would you like to trigger this webhook?: `Just the push event.`
- Active: `Ticked`

You will link CodeBuild to GitHub [next](#codebuild).

### AWS
#### CodeBuild
You must
[configure your build](https://docs.aws.amazon.com/codebuild/latest/userguide/create-project.html)
to integrate with GitHub. For the `Source provider` option choose GitHub then `Connect to GitHub`.
Follow the authentication path then pick the source repository.

The following options should be used:
- Report build status: `Ticked`
- Webhook: `Ticked`
- Branch filter: `Leave blank` (Build them all!)
- Build Badge: `Ticked`
- Build specification: `Use the buildspec.yml in the source code root directory`
- Buildspec name: `buildspec.yml`
- Service role: `Create a service role in your account`

#### DynamoDB
To maintain the state of multiple builds, a [DynamoDB table](
https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithTables.html)
with a partition and sort key needs to be created. The [example app file](#app) uses the following
values:

    dynamo:
        table_name: 'build-status'
        partition_key_name: 'branch_name'
        sort_key_name: 'build_start_time'

The primary partition key is a `String` and the primary sort key is a `Number`.

#### Systems Manager (SSM)
To POST to GitHub a `github_owner` and `github_token` are [required](#github). These are to
be kept in the [AWS Systems Manager Parameter Store](
https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-paramstore.html)
as type `SecureString`.

#### IAM
You will be creating an IAM service role when configuring [CodeBuild](#codebuild).

### Config
Two configuration files are required for the scripts: `app` and `user`. Examples are located at
`py_dev_hammer/examples/{type}_config.example.yml`.

#### App
The example app config can be copied and used as is, however you may want to remove some of the test
types under `tests_to_run` and note that your [`buildspec.yml`](#usage) will need to be adjusted to
match. 

#### User
The example user config should be modified to suit your GitHub and AWS project details.

### Certificates
To POST securely to GitHub (as you are sending your GitHub token over the Internet) a certificate
must be used. Pass your file path as an environment variable `CERTIFICATE_FILE`. Alternatively you
can use the third-party Python module [certifi](https://pypi.org/project/certifi/) to generate this.
The script will look for the environment variable first and fall back to using `certifi.where()`.

### Environment variables
A number of environment variables must be set for the CodeBuild environment via the
[`buildspec.yml`](#usage) file.

This variable is set automatically by AWS CodeBuild:
 - CODEBUILD_SRC_DIR

These variables are used by the scripts of this project:  
(Note: the back-ticks are important as this is BASH-land)
- PYTHONPATH=`` `pwd` ``
- CONFIG_DIR=`/path/to/your/config/dir`
- CERTIFICATE_FILE=`/path/to/your/cert.file` (Note: [optional](#certificates))
- CODEBUILD_GIT_BRANCH=`` `git branch -a --contains HEAD | sed -n 2p | awk '{ printf $1 }'` ``  
(Note: deprecation warning; will be sourced from within Python in future releases)

This variable is used by CodeBuild:
- TESTS_DIR=`$CODEBUILD_SRC_DIR/path/to/your/tests/results/dir`  
(Note: this is the test directory for your project, not this project)

## Usage
Create a Python file to run the scripts from the command line via `buildspec.yml`. An example file
can be found in `py_dev_hammer/examples/run_github_status_posting.py`.

To use CodeBuild with the above [AWS config](#codebuild), you will need to create a `buildspec.yml`
file. An example file is located in `py_dev_hammer/examples/buildspec.yml`. The `build` section of
that file is where you will call the [`tests_to_run`](#app).

## Road Map
- Set up all AWS resources with CloudFormation (who wants to read this README?)
- reStructuredText to Markdown converter (mostly already written)
- Visualisation of the toolkit with dashboards (need more tools in the old toolkit first)
- Dockerising things (that should be Dockerised)
- Other cool things I'm sure (fingers crossed)
