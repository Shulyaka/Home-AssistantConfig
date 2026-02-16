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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.components.conversation import async_converse
from homeassistant.components.telegram_bot import (
    ATTR_CHAT_ID,
    ATTR_MESSAGE,
    ATTR_TARGET,
    DOMAIN as TELEGRAM_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.components.telegram_bot.const import (
    ATTR_PARSER,
    ATTR_TEXT,
    ATTR_USER_ID,
    EVENT_TELEGRAM_TEXT,
)
from homeassistant.helpers.chat_session import CONVERSATION_TIMEOUT, DATA_CHAT_SESSION
from homeassistant.util import dt as dt_util
from telegram.helpers import escape_markdown
import re
import logging
from datetime import timedelta

DOMAIN = "telegram_bot_conversation"

TELEGRAM_CONVERSATION_TIMEOUT = timedelta(hours=24)

_LOGGER = logging.getLogger(__name__)

user_id_map = {}


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    async def send_message(
        target: str, message: str, context: Context | None = None
    ) -> dict:
        if context is None:
            context = Context()

        if len(message) > 4096:
            messages = {"chats": []}
            # Split the message in chunks
            while len(message) > 4096:
                # First try to split by paragraph
                if (i := message.rfind("\n\n", 0, 4096)) > 0:
                    i += 2
                # Then try to split by newline
                elif (i := message.rfind("\n", 0, 4096)) > 0:
                    i += 1
                # Then try to split by sentence
                elif (i := message.rfind(". ", 0, 4096)) > 0:
                    i += 2
                # Then try to split by semi-sentence
                elif (i := message.rfind("; ", 0, 4096)) > 0:
                    i += 2
                # Then try to split by comma
                elif (i := message.rfind(", ", 0, 4096)) > 0:
                    i += 2
                # Then try to split by word
                elif (i := message.rfind(" ", 0, 4096)) > 0:
                    i += 1
                # If all failed, split by position
                else:
                    i = 4096

                chunk_messages = await send_message(target, message[:i], context)
                message = message[i:]
                messages["chats"].extend(chunk_messages["chats"])

            if len(message) > 0:
                chunk_messages = await send_message(target, message, context)
                messages["chats"].extend(chunk_messages["chats"])

            return messages

        try:
            # First try: markdownv2
            return await hass.services.async_call(
                TELEGRAM_DOMAIN,
                SERVICE_SEND_MESSAGE,
                {
                    ATTR_MESSAGE: message,
                    ATTR_TARGET: target,
                    ATTR_PARSER: "markdownv2",
                },
                blocking=True,
                context=context,
                return_response=True,
            )
        except HomeAssistantError as e:
            _LOGGER.exception(e, stack_info=True)

        try:
            # Second try: markdown
            return await hass.services.async_call(
                TELEGRAM_DOMAIN,
                SERVICE_SEND_MESSAGE,
                {
                    ATTR_MESSAGE: message,
                    ATTR_TARGET: target,
                    ATTR_PARSER: "markdown",
                },
                blocking=True,
                context=context,
                return_response=True,
            )
        except HomeAssistantError as e:
            _LOGGER.exception(e, stack_info=True)
            pass

        # Third try: plain_text
        return await hass.services.async_call(
            TELEGRAM_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                # ATTR_MESSAGE: escape_markdown(message),
                ATTR_MESSAGE: message,
                ATTR_TARGET: target,
                ATTR_PARSER: "plain_text",
            },
            blocking=True,
            context=context,
            return_response=True,
        )

    async def text_events(event: Event):
        # Only deal with private chats.
        if event.data[ATTR_CHAT_ID] != event.data[ATTR_USER_ID]:
            return

        conversation_id = f"telegram_{event.data[ATTR_CHAT_ID]}"
        context = event.context
        if context.user_id is None:
            context.user_id = user_id_map.get(
                event.data[ATTR_USER_ID], user_id_map.get(event.data[ATTR_CHAT_ID])
            )

        conversation_result = await async_converse(
            hass,
            text=event.data[ATTR_TEXT],
            conversation_id=conversation_id,
            context=context,
            # agent_id='2ff759d8c03b62d828dacfc7f46edef9',
            # agent_id='conversation.o3_mini',
            # agent_id="conversation.openai_conversation",
            # agent_id="conversation.claude",
            agent_id="conversation.gpt_5",
        )

        all_sessions = hass.data[DATA_CHAT_SESSION]
        if (session := all_sessions.get(conversation_id)) is not None:
            session.last_updated = (
                dt_util.utcnow() + TELEGRAM_CONVERSATION_TIMEOUT - CONVERSATION_TIMEOUT
            )

        messages = await send_message(
            target=event.data[ATTR_USER_ID],
            message=conversation_result.response.speech["plain"]["speech"],
            context=context,
        )

        _LOGGER.debug("messages=%s", messages)

    hass.bus.async_listen(EVENT_TELEGRAM_TEXT, text_events)
    return True
