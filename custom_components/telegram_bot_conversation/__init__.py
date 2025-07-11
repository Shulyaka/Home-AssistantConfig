# This is a highly experimental integration, use at your own risk!
#
# This integration ties up the Home Assistant conversation
# integration with the telegram_bot integration.
#
# If you have Telegram & Almond installed and configured,
# this integration will hook them up together.
#
# It passes chat flowing in from Telegram into Almond
# and sending back the response.
#
# This allows you to "Talk" to your Home Assistant in
# a more natural "Human" language.
#
# Requires telegram_bot to be set up.
#
from homeassistant.core import Context, Event, HomeAssistant
from homeassistant.components.conversation import async_converse
from homeassistant.components.telegram_bot import (
    ATTR_CHAT_ID,
    ATTR_MESSAGE,
    ATTR_TARGET,
    ATTR_TEXT,
    ATTR_USER_ID,
    DOMAIN as TELEGRAM_DOMAIN,
    EVENT_TELEGRAM_TEXT,
    SERVICE_SEND_MESSAGE,
)
from telegram.helpers import escape_markdown
import re
import logging

DOMAIN = "telegram_bot_conversation"

_LOGGER = logging.getLogger(__name__)

conversation_id_map = {}


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    async def text_events(event: Event):
        # Only deal with private chats.
        if event.data[ATTR_CHAT_ID] != event.data[ATTR_USER_ID]:
            return

        # Handled by a separate automation:
        if re.search(r"https://(www.|)youtu*", event.data[ATTR_TEXT]):
            return

        if event.data[ATTR_CHAT_ID] in conversation_id_map:
            conversation_id = conversation_id_map[event.data[ATTR_CHAT_ID]]
        else:
            conversation_id = None

        conversation_result = await async_converse(
            hass,
            text=event.data[ATTR_TEXT],
            conversation_id=conversation_id,
            context=event.context,
            # agent_id='2ff759d8c03b62d828dacfc7f46edef9',
            # agent_id='conversation.o3_mini',
            # agent_id="conversation.openai_conversation",
            agent_id="conversation.claude",
        )

        conversation_id_map[event.data[ATTR_CHAT_ID]] = (
            conversation_result.conversation_id
        )

        await hass.services.async_call(
            TELEGRAM_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                # ATTR_MESSAGE: escape_markdown(conversation_result.response.speech["plain"]["speech"]),
                ATTR_MESSAGE: conversation_result.response.speech["plain"]["speech"],
                ATTR_TARGET: event.data[ATTR_USER_ID],
                # "parse_mode": "markdownv2",
            },
        )

    hass.bus.async_listen(EVENT_TELEGRAM_TEXT, text_events)
    return True
