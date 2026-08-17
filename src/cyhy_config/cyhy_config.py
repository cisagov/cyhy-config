"""Finds a CyHy configuration.

This module provides a function to find a CyHy configuration file.

It will search in the following locations, in this order:
 1. A location passed in as a parameter
 2. Environment variable for an SSM parameter path
 3. Environment variable for a file path
 4. The current working directory
 5. The user's home directory
 6. The system's /etc directory
"""

# Standard Python Libraries
import logging
import os
from os import environ
from pathlib import Path
import pprint
import tomllib
from typing import Literal, TypeVar, overload

# Third-Party Libraries
from boto3 import client
from botocore.exceptions import ClientError
from pydantic import BaseModel, ValidationError

CONFIG_PATH_CWD = Path("cyhy.toml")
CONFIG_PATH_ETC = Path("/etc/cyhy.toml")
CONFIG_PATH_HOME = Path.home() / ".cyhy/cyhy.toml"
CYHY_CONFIG_PATH_ENV = "CYHY_CONFIG_PATH"
CYHY_CONFIG_SSM_PATH_ENV = "CYHY_CONFIG_SSM_PATH"

# Ensure the logger is under the common CyHy namespace
logger = logging.getLogger(f"cyhy.{__name__}")
pp = pprint.PrettyPrinter(indent=4)

# Define a TypeVar that is bound to BaseModel
T = TypeVar("T", bound=BaseModel)


# We use function overloading to provide different return types
# depending on the arguments passed to the function.  Without it,
# mypy would not be able to infer the return type of the function.


@overload
def get_config(
    *,
    file_path: str | None = ...,
    ssm_path: str | None = ...,
    model: Literal[None],
) -> dict:
    pass  # pragma: no cover


@overload
def get_config(
    *,
    file_path: str | None = ...,
    ssm_path: str | None = ...,
    model: type[T],
) -> T:
    pass  # pragma: no cover


def get_config(
    file_path: str | None = None,
    ssm_path: str | None = None,
    model: type[T] | None = None,
) -> T | dict:
    """Get the CyHy configuration."""
    # First we try to find the configuration file in SSM
    # If we can't find it there, we look for it in a file
    config = read_config_ssm(ssm_path, model)
    if config:
        return config

    # We didn't find the configuration in SSM, so we look for it in a file
    config_file_path = find_config_file(file_path)

    return read_config_file(config_file_path, model)


def find_config_file(file_path: str | None = None) -> Path:
    """Find a CyHy configuration file.

    Args:
        file_path: A path to a configuration file.

    Returns:
        A path to a CyHy configuration file.

    Raises:
        FileNotFoundError: If no configuration file is found.
    """
    # Check if the provided path exists
    if file_path:
        if Path(file_path).exists():
            logger.debug("Using configuration file passed as parameter: %s", file_path)
            return Path(file_path)
        else:
            logger.warning(
                "Configuration file passed as parameter not found: %s", file_path
            )

    # Check environment variable for file path
    env_file_value = environ.get(CYHY_CONFIG_PATH_ENV, None)
    if env_file_value:
        env_path = Path(env_file_value)
        if env_path.exists():
            logger.debug(
                "Using configuration file from environment variable: %s", env_path
            )
            return env_path
        else:
            logger.warning(
                "Configuration file from environment variable not found: %s", env_path
            )

    # Check the current working directory
    if CONFIG_PATH_CWD.exists():
        logger.debug(
            "Using configuration file from current working directory: %s",
            CONFIG_PATH_CWD,
        )
        return CONFIG_PATH_CWD

    # Check the user's home directory
    if CONFIG_PATH_HOME.exists():
        logger.debug(
            "Using configuration file from home directory: %s", CONFIG_PATH_HOME
        )
        return CONFIG_PATH_HOME

    # Check the system's /etc directory
    if CONFIG_PATH_ETC.exists():
        logger.debug(
            "Using configuration file from /etc directory: %s", CONFIG_PATH_ETC
        )
        return CONFIG_PATH_ETC

    # If no configuration file is found, raise an exception
    logger.error("No CyHy configuration file found.")
    raise FileNotFoundError("No CyHy configuration file found.")


def read_config_ssm(
    ssm_path: str | None = None, model: type[T] | None = None
) -> T | dict | None:
    """Read the configuration from SSM and return its contents as a dictionary."""
    ssm_paths = [
        (ssm_path, "path"),
        (environ.get(CYHY_CONFIG_SSM_PATH_ENV, None), "environment variable"),
    ]

    for path, source in ssm_paths:
        logger.debug("Checking SSM parameter from %s: %s", source, path)
        if path:
            ssm = client("ssm")
            try:
                response = ssm.get_parameter(Name=path, WithDecryption=True)
            except ClientError as e:
                if e.response["Error"]["Code"] == "ParameterNotFound":
                    logger.warning("SSM parameter not found: %s", path)
                    # Try the next source rather than giving up. Returning here
                    # skipped the environment variable whenever an explicit path
                    # was passed but not present in SSM. The function still
                    # returns None once every source has been tried.
                    continue
                else:
                    logger.error(e)
                    raise e

            param_value = response["Parameter"]["Value"]
            logger.debug("Using configuration file from SSM %s: %s", source, path)
            try:
                config_dict = tomllib.loads(param_value)
            except tomllib.TOMLDecodeError as e:
                logger.error("Error decoding TOML: %s", param_value)
                raise e

            return validate_config(config_dict, model)

    return None


def read_config_file(config_file: Path, model: type[T] | None = None) -> T | dict:
    """Read the configuration file and return its contents as a dictionary."""
    if not os.path.isfile(config_file):
        logger.error("Config file not found: %s", config_file)
        raise FileNotFoundError(f"Config file not found: {config_file}")

    try:
        logger.debug("Reading config file: %s", config_file)
        with open(config_file, "rb") as f:
            config_dict = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        logger.error("Error decoding TOML file: %s", config_file)
        raise e

    return validate_config(config_dict, model)


def validate_config(config_dict: dict, model: type[T] | None) -> T | dict:
    """Validate the configuration against the model."""
    if not model:
        logger.info("No model provided, returning config as a dictionary.")
        logger.debug("Parsed configuration:\n%s", pp.pformat(config_dict))
        return config_dict
    try:
        config = model(**config_dict)
        logger.debug("Validated configuration:\n%s", pp.pformat(config.model_dump()))
        return config
    except ValidationError as e:
        logger.error(e)
        raise e
