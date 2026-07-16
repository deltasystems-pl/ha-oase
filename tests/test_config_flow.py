"""Tests for the OASE config flow."""

from __future__ import annotations

from unittest.mock import MagicMock

from pyoase import OaseAuthError, OaseConnectionError

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.oase.const import CONF_EMAIL, CONF_PASSWORD, DOMAIN

from .conftest import GATEWAY_ID

USER_INPUT = {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "hunter2"}


async def test_user_flow_success(
    hass: HomeAssistant,
    mock_auth: MagicMock,
    mock_client: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """A valid login creates a config entry keyed by the first gateway id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OASE FM-Master"
    assert result["data"][CONF_EMAIL] == "test@example.com"
    assert result["result"].unique_id == GATEWAY_ID
    mock_auth.return_value.async_login.assert_awaited_once()


async def test_user_flow_invalid_auth(
    hass: HomeAssistant, mock_auth: MagicMock, mock_client: MagicMock
) -> None:
    """Bad credentials surface as an ``invalid_auth`` form error and recover."""
    mock_auth.return_value.async_login.side_effect = OaseAuthError("bad password")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Recover on a subsequent, valid attempt.
    mock_auth.return_value.async_login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_auth: MagicMock, mock_client: MagicMock
) -> None:
    """A connection error surfaces as a ``cannot_connect`` form error."""
    mock_auth.return_value.async_login.side_effect = OaseConnectionError("boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_auth: MagicMock,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A second entry for the same gateway aborts as already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_auth: MagicMock,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Reauth revalidates and updates the stored password."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"
