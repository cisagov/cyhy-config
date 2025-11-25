# cyhy-config 📝 #

[![GitHub Build Status](https://github.com/cisagov/cyhy-config/workflows/build/badge.svg)](https://github.com/cisagov/cyhy-config/actions)
[![License](https://img.shields.io/github/license/cisagov/cyhy-config)](https://spdx.org/licenses/)
[![CodeQL](https://github.com/cisagov/cyhy-config/workflows/CodeQL/badge.svg)](https://github.com/cisagov/cyhy-config/actions/workflows/codeql-analysis.yml)
[![Coverage Status](https://coveralls.io/repos/github/cisagov/cyhy-config/badge.svg?branch=develop)](https://coveralls.io/github/cisagov/cyhy-config?branch=develop)
[![Code Style](https://img.shields.io/badge/Code%20Style-black-black)](https://github.com/psf/black)

This repository implements a Python module for reading [TOML](https://toml.io)
configuration files used by various Cyber Hygiene components.  It will discover,
read, and optionally validate a configuration file.

## Search Procedure ##

The module will search for the configuration file in the following locations, in
the specified order:

1. The path in the filesystem specified by the optional `CYHY_CONFIG_PATH`
   environment variable.
1. The path in [AWS SSM](https://docs.aws.amazon.com/systems-manager/) specified
   by the optional `CYHY_CONFIG_SSM_PATH` environment variable.
1. In the current working directory: `cyhy.toml`
1. In the user's home directory: `~/.cyhy/cyhy.toml`
1. In the system's `etc` directory: `/etc/cyhy.toml`

If the configuration file is not found, the module will raise a
`FileNotFoundError`.

## Configuration File Validation ##

The module will optionally validate the configuration file against a
[Pydantic](https://docs.pydantic.dev) model.  If the configuration file does not
match the model a
[`ValidationError`](https://docs.pydantic.dev/latest/api/pydantic_core/#pydantic_core.ValidationError)
will be raised.

## Environment Variables ##

| Variable | Description |
|----------|-------------|
| `CYHY_CONFIG_PATH` | The path to the configuration file. |
| `CYHY_CONFIG_SSM_PATH` | The path to the configuration file in AWS SSM. |

## Example Usage ##

```python
from cyhy_config import get_config
from pydantic import ValidationError

try:
    config = get_config(file_path=config_file, model=MyModelClass)
except ValidationError:
    sys.exit(1)
except FileNotFoundError:
    sys.exit(1)
```

## Contributing ##

We welcome contributions!  Please see [`CONTRIBUTING.md`](CONTRIBUTING.md) for
details.

## License ##

This project is in the worldwide [public domain](LICENSE).

This project is in the public domain within the United States, and copyright and
related rights in the work worldwide are waived through the [CC0 1.0 Universal
public domain dedication](https://creativecommons.org/publicdomain/zero/1.0/).

All contributions to this project will be released under the CC0 dedication. By
submitting a pull request, you are agreeing to comply with this waiver of
copyright interest.
