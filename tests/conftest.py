"""Fixtures for the OASE integration tests."""

from __future__ import annotations

from collections.abc import Generator
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from pyoase import Inventory
import pytest

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.oase.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_TOKEN_DATA,
    DOMAIN,
)

GATEWAY_ID = "00000000-0000-4000-8000-000000000001"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> Generator[None]:
    """Enable loading of the custom integration in every test."""
    yield


def load_inventory() -> Inventory:
    """Load the synthetic inventory fixture as an :class:`Inventory`."""
    path = Path(__file__).parent / "fixtures" / "inventory.json"
    return Inventory.from_dict(json.loads(path.read_text(encoding="utf-8")))


@pytest.fixture
def inventory() -> Inventory:
    """Return the parsed synthetic inventory."""
    return load_inventory()


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry pre-loaded with fake credentials."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="OASE FM-Master",
        unique_id=GATEWAY_ID,
        data={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "hunter2",
            CONF_TOKEN_DATA: {"refresh_token": "fake-refresh-token"},
        },
    )


@pytest.fixture
def mock_auth() -> Generator[MagicMock]:
    """Patch OaseAuth everywhere it is imported and return the class mock."""
    with (
        patch("custom_components.oase.OaseAuth", autospec=True) as auth_cls,
        patch("custom_components.oase.config_flow.OaseAuth", new=auth_cls),
    ):
        auth = auth_cls.return_value
        auth.async_login = AsyncMock(return_value="fake-access-token")
        auth.async_get_access_token = AsyncMock(return_value="fake-access-token")
        auth.token_data = {"refresh_token": "fake-refresh-token"}
        yield auth_cls


@pytest.fixture
def mock_client(inventory: Inventory) -> Generator[MagicMock]:
    """Patch OaseCloudClient everywhere it is imported and return the class mock."""
    with (
        patch("custom_components.oase.OaseCloudClient", autospec=True) as client_cls,
        patch("custom_components.oase.config_flow.OaseCloudClient", new=client_cls),
    ):
        client = client_cls.return_value
        client.async_get_inventory = AsyncMock(return_value=inventory)
        client.async_set_socket = AsyncMock(return_value=True)
        client.async_set_dimmer_value = AsyncMock(return_value=True)
        # EGC device reads the coordinator performs while enriching state; give
        # concrete values so no mock objects leak into entity state / diagnostics.
        client.async_get_device_on = AsyncMock(return_value=True)
        client.async_get_pump_power = AsyncMock(return_value=128)
        client.async_get_led_channels = AsyncMock(return_value=[])
        client.async_get_operating_hours = AsyncMock(return_value=100)
        client.async_get_software_version = AsyncMock(return_value="1.0")
        client.async_set_device_on = AsyncMock(return_value=None)
        client.async_set_pump_power = AsyncMock(return_value=None)
        client.async_set_pump_show = AsyncMock(return_value=True)
        client.async_set_led_channel = AsyncMock(return_value=True)
        yield client_cls


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent the platforms from being set up during config-flow tests."""
    with patch(
        "custom_components.oase.async_setup_entry", return_value=True
    ) as setup_entry:
        yield setup_entry
