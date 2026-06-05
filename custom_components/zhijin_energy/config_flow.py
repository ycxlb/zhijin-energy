"""Config flow for Zhijin Energy."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_TOKEN
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .api import ZhijinEnergyAPI, APIError


class ZhijinEnergyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # 验证 token 和设备ID有效性
            session = async_get_clientsession(self.hass)
            api = ZhijinEnergyAPI(session, user_input[CONF_TOKEN])

            try:
                device_info = await api.get_device_info(user_input["device_id"])
                if device_info:
                    return self.async_create_entry(
                        title=f"{device_info.get('machine_name', '太阳能控制器')} {user_input['device_id']}",
                        data=user_input,
                    )
                errors["base"] = "device_not_found"
            except APIError:
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_TOKEN): str,
                vol.Required("device_id", default=29673): int,
            }),
            errors=errors,
        )
