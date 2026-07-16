"""Config flow for the OASE integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from pyoase import OaseAuth, OaseAuthError, OaseCloudClient, OaseConnectionError, OaseError

from .const import CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN_DATA, DOMAIN

_LOGGER = logging.getLogger(__name__)

TITLE = "OASE FM-Master"

_EMAIL_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL))
_PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): _EMAIL_SELECTOR,
        vol.Required(CONF_PASSWORD): _PASSWORD_SELECTOR,
    }
)
STEP_REAUTH_DATA_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): _PASSWORD_SELECTOR})


class OaseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OASE."""

    VERSION = 1

    async def _async_validate(
        self, email: str, password: str
    ) -> tuple[dict[str, Any] | None, str | None, dict[str, str]]:
        """Validate credentials against the OASE cloud.

        Returns ``(entry_data, unique_id, errors)``. ``entry_data`` is ``None``
        when validation failed and ``errors`` describes why.
        """
        session = async_get_clientsession(self.hass)
        auth = OaseAuth(session, email, password)
        client = OaseCloudClient(session, auth)
        try:
            await auth.async_login()
            inventory = await client.async_get_inventory()
        except OaseAuthError:
            return None, None, {"base": "invalid_auth"}
        except OaseConnectionError:
            return None, None, {"base": "cannot_connect"}
        except OaseError:
            _LOGGER.exception("Unexpected OASE error while validating credentials")
            return None, None, {"base": "unknown"}
        except Exception:  # noqa: BLE001 - surface anything unexpected as "unknown"
            _LOGGER.exception("Unexpected error while validating OASE credentials")
            return None, None, {"base": "unknown"}

        if not inventory.gateways:
            return None, None, {"base": "no_devices"}

        # Prefer a stable gateway id; fall back to something account-scoped.
        unique_id = inventory.gateways[0].id
        entry_data = {
            CONF_EMAIL: email,
            CONF_PASSWORD: password,
            CONF_TOKEN_DATA: auth.token_data,
        }
        return entry_data, unique_id, {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step: collect and validate credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            entry_data, unique_id, errors = await self._async_validate(
                user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
            if entry_data is not None and unique_id is not None:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=TITLE, data=entry_data)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start a reauthentication flow after the token became invalid."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication by re-entering the password."""
        reauth_entry = self._get_reauth_entry()
        email = reauth_entry.data[CONF_EMAIL]
        errors: dict[str, str] = {}
        if user_input is not None:
            entry_data, _unique_id, errors = await self._async_validate(
                email, user_input[CONF_PASSWORD]
            )
            if entry_data is not None:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_TOKEN_DATA: entry_data[CONF_TOKEN_DATA],
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            description_placeholders={CONF_EMAIL: email},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow the user to change the stored credentials."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            entry_data, unique_id, errors = await self._async_validate(
                user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
            if entry_data is not None and unique_id is not None:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    reconfigure_entry, data_updates=entry_data
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                {CONF_EMAIL: reconfigure_entry.data.get(CONF_EMAIL)},
            ),
            errors=errors,
        )
