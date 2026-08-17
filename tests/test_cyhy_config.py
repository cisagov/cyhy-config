"""Tests for cyhy_config."""

# Standard Python Libraries
import os
from pathlib import Path
import tomllib
from unittest.mock import MagicMock, mock_open, patch

# Third-Party Libraries
from botocore.exceptions import ClientError
from pydantic import BaseModel, ValidationError
import pytest

# cisagov Libraries
from cyhy_config import __version__
from cyhy_config.cyhy_config import (
    CONFIG_PATH_CWD,
    CONFIG_PATH_ETC,
    CONFIG_PATH_HOME,
    CYHY_CONFIG_PATH_ENV,
    CYHY_CONFIG_SSM_PATH_ENV,
    find_config_file,
    get_config,
    read_config_file,
    read_config_ssm,
    validate_config,
)


class TestModel(BaseModel):
    """A simple model for testing."""

    key: str


# define sources of version strings
RELEASE_TAG = os.getenv("RELEASE_TAG")
PROJECT_VERSION = __version__


@pytest.mark.skipif(
    RELEASE_TAG in [None, ""], reason="this is not a release (RELEASE_TAG not set)"
)
def test_release_version():
    """Verify that release tag version agrees with the module version."""
    assert (
        RELEASE_TAG == f"v{PROJECT_VERSION}"
    ), "RELEASE_TAG does not match the project version"


def test_find_config_file_given_path_exists():
    """Test find_config_file when the given path exists."""
    with patch("cyhy_config.cyhy_config.Path.exists", return_value=True):
        assert find_config_file("/mock/path") == Path("/mock/path")


def test_find_config_file_given_path_does_not_exist():
    """Test find_config_file when the given path does not exist."""
    with patch("cyhy_config.cyhy_config.Path.exists", side_effect=[False, True]):
        assert find_config_file("/mock/path") == CONFIG_PATH_CWD


def test_find_config_file_env_var_set():
    """Test find_config_file when the CYHY_CONFIG_PATH environment variable is set."""
    with patch.dict(os.environ, {CYHY_CONFIG_PATH_ENV: "/mock/env/path"}):
        with patch("cyhy_config.cyhy_config.Path.exists", return_value=True):
            assert find_config_file() == Path("/mock/env/path")


def test_find_config_file_env_var_set_but_does_not_exist():
    """Test find_config_file when CYHY_CONFIG_PATH env var is set but does not exist."""
    with patch.dict(os.environ, {CYHY_CONFIG_PATH_ENV: "/mock/env/path"}):
        with patch("cyhy_config.cyhy_config.Path.exists", side_effect=[False, True]):
            assert find_config_file() == CONFIG_PATH_CWD


def test_find_config_file_in_current_directory():
    """Test find_config_file when the cyhy.toml file exists in the current directory."""
    with patch("cyhy_config.cyhy_config.Path.exists", side_effect=[True]):
        assert find_config_file() == CONFIG_PATH_CWD


def test_find_config_file_in_home_directory():
    """Test find_config_file when the cyhy.toml file exists in user's home dir."""
    with patch("cyhy_config.cyhy_config.Path.exists", side_effect=[False, True]):
        assert find_config_file() == CONFIG_PATH_HOME


def test_find_config_file_in_etc_directory():
    """Test find_config_file when the cyhy.toml file exists in the /etc directory."""
    with patch("cyhy_config.cyhy_config.Path.exists", side_effect=[False, False, True]):
        assert find_config_file() == CONFIG_PATH_ETC


def test_find_config_file_no_valid_path():
    """Test find_config_file when no valid path is found."""
    with patch("cyhy_config.cyhy_config.Path.exists", return_value=False):
        with pytest.raises(FileNotFoundError):
            find_config_file()


def test_read_config_ssm_env_var_set():
    """Test read_config_ssm when the CYHY_CONFIG_SSM_PATH env var is set."""
    mock_ssm_client = MagicMock()
    mock_ssm_client.get_parameter.return_value = {
        "Parameter": {"Value": 'key = "value"'}
    }

    with patch("cyhy_config.cyhy_config.client", return_value=mock_ssm_client):
        with patch.dict(os.environ, {CYHY_CONFIG_SSM_PATH_ENV: "/mock/ssm/path"}):
            config = read_config_ssm(model=TestModel)
            assert config.key == "value"


def test_read_config_ssm_parameter_not_found():
    """Test read_config_ssm when the parameter is not found in AWS SSM."""
    mock_ssm_client = MagicMock()
    mock_ssm_client.get_parameter.side_effect = ClientError(
        {"Error": {"Code": "ParameterNotFound"}}, "get_parameter"
    )

    with patch("cyhy_config.cyhy_config.client", return_value=mock_ssm_client):
        with patch.dict(os.environ, {CYHY_CONFIG_SSM_PATH_ENV: "/mock/ssm/bad_path"}):
            assert read_config_ssm() is None


def test_read_config_ssm_falls_back_to_env_var():
    """Test read_config_ssm tries the env var when the given path is not in SSM."""
    good_path = "/mock/ssm/good_path"

    def get_parameter(Name, WithDecryption=False):
        if Name == good_path:
            return {"Parameter": {"Value": 'key = "value"'}}
        raise ClientError({"Error": {"Code": "ParameterNotFound"}}, "get_parameter")

    mock_ssm_client = MagicMock()
    mock_ssm_client.get_parameter.side_effect = get_parameter

    with patch("cyhy_config.cyhy_config.client", return_value=mock_ssm_client):
        with patch.dict(os.environ, {CYHY_CONFIG_SSM_PATH_ENV: good_path}):
            config = read_config_ssm("/mock/ssm/bad_path", model=TestModel)
            assert config.key == "value"

    # Both sources should have been consulted, in the documented order.
    queried = [
        call.kwargs["Name"] for call in mock_ssm_client.get_parameter.call_args_list
    ]
    assert queried == ["/mock/ssm/bad_path", good_path]


def test_read_config_ssm_no_source_found():
    """Test read_config_ssm returns None when no source has the parameter."""
    mock_ssm_client = MagicMock()
    mock_ssm_client.get_parameter.side_effect = ClientError(
        {"Error": {"Code": "ParameterNotFound"}}, "get_parameter"
    )

    with patch("cyhy_config.cyhy_config.client", return_value=mock_ssm_client):
        with patch.dict(os.environ, {CYHY_CONFIG_SSM_PATH_ENV: "/mock/ssm/also_bad"}):
            assert read_config_ssm("/mock/ssm/bad_path") is None


def test_read_config_ssm_other_client_error():
    """Test read_config_ssm when SSM responds with non-ParameterNotFound error code."""
    mock_ssm_client = MagicMock()
    mock_ssm_client.get_parameter.side_effect = ClientError(
        {"Error": {"Code": "SchrödingersParameterError"}}, "get_parameter"
    )

    with patch("cyhy_config.cyhy_config.client", return_value=mock_ssm_client):
        with patch.dict(os.environ, {CYHY_CONFIG_SSM_PATH_ENV: "/mock/ssm/bad_path"}):
            with pytest.raises(ClientError):
                read_config_ssm()


def test_read_config_ssm_invalid_toml():
    """Test read_config_ssm when SSM returns bad TOML data."""
    mock_ssm_client = MagicMock()
    mock_ssm_client.get_parameter.return_value = {
        "Parameter": {"Value": "This is not valid TOML"}
    }

    with patch("cyhy_config.cyhy_config.client", return_value=mock_ssm_client):
        with patch.dict(os.environ, {CYHY_CONFIG_SSM_PATH_ENV: "/mock/ssm/path"}):
            with pytest.raises(tomllib.TOMLDecodeError):
                read_config_ssm()


def test_read_config_ssm_no_ssm_paths():
    """Test read_config_ssm when no SSM paths are provided."""
    assert read_config_ssm() is None


def test_read_config_file_file_exists():
    """Test read_config_file when the file exists."""
    mock_file_data = b'key = "value"'
    with patch("os.path.isfile", return_value=True):
        with patch("builtins.open", mock_open(read_data=mock_file_data)):
            with patch(
                "cyhy_config.cyhy_config.tomllib.load", return_value={"key": "value"}
            ):
                config = read_config_file(Path("/mock/path"), model=TestModel)
                assert config.key == "value"


def test_read_config_file_file_not_found():
    """Test read_config_file when the file does not exist."""
    with patch("os.path.isfile", return_value=False):
        with pytest.raises(FileNotFoundError):
            read_config_file(Path("/mock/path"))


def test_read_config_file_invalid_toml():
    """Test read_config_file when the TOML data is invalid."""
    mock_file_data = b'key = "value"'
    with patch("os.path.isfile", return_value=True):
        with patch("builtins.open", mock_open(read_data=mock_file_data)):
            with patch(
                "cyhy_config.cyhy_config.tomllib.load",
                side_effect=tomllib.TOMLDecodeError("Error", "doc", 0),
            ):
                with pytest.raises(tomllib.TOMLDecodeError):
                    read_config_file(Path("/mock/path"))


def test_validate_config_valid_dict():
    """Test validate_config with a valid config dictionary."""
    config_dict = {"key": "value"}
    config = validate_config(config_dict, TestModel)
    assert config.key == "value"


def test_validate_config_empty_dict():
    """Test validate_config with an empty config dictionary."""
    with pytest.raises(ValidationError):
        validate_config({}, TestModel)


def test_validate_config_no_model():
    """Test validate_config with no model provided."""
    config_dict = {"key": "value"}
    config = validate_config(config_dict, None)
    assert config == config_dict


def test_get_config_from_ssm():
    """Test the get_config function when the config is retrieved from AWS SSM."""
    with patch(
        "cyhy_config.cyhy_config.read_config_ssm", return_value={"key": "value"}
    ):
        config = get_config(model=TestModel)
        assert config["key"] == "value"


def test_get_config_fallback_to_file():
    """Test get_config fallback from SSM to file."""
    with patch("cyhy_config.cyhy_config.read_config_ssm", return_value=None):
        with patch(
            "cyhy_config.cyhy_config.find_config_file", return_value=Path("/mock/path")
        ):
            with patch(
                "cyhy_config.cyhy_config.read_config_file",
                return_value={"key": "value"},
            ):
                config = get_config(model=TestModel)
                assert config["key"] == "value"
