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
from homeassistant.core import Context, Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.components.conversation import (
    async_converse,
    get_agent_manager,
    DATA_COMPONENT,
    ConversationEntity,
    ChatLog,
    async_get_chat_log,
)
from homeassistant.components.telegram_bot import (
    ATTR_CHAT_ID,
    ATTR_MESSAGE,
    DOMAIN as TELEGRAM_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.components.telegram_bot.const import (
    ATTR_KEYBOARD_INLINE,
    ATTR_PARSER,
    ATTR_TEXT,
    ATTR_USER_ID,
    ATTR_TARGET,
    EVENT_TELEGRAM_TEXT,
    EVENT_TELEGRAM_COMMAND,
    EVENT_TELEGRAM_CALLBACK,
    SERVICE_ANSWER_CALLBACK_QUERY,
    ATTR_CALLBACK_QUERY_ID,
    CONF_CONFIG_ENTRY_ID,
    ATTR_CHAT_ACTION,
    CHAT_ACTION_TYPING,
    SERVICE_SEND_CHAT_ACTION,
    ATTR_MESSAGE_THREAD_ID,
)
from homeassistant.helpers.chat_session import (
    CONVERSATION_TIMEOUT,
    async_get_chat_session,
)
from homeassistant.util import dt as dt_util
import logging
from datetime import timedelta
from typing import Any
from homeassistant.components.telegram_bot.const import (
    SUBENTRY_TYPE_ALLOWED_CHAT_IDS,
    CONF_CHAT_ID,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.intent import IntentResponseType
from telegramify_markdown import markdownify

from .const import (
    CONF_CONVERSATION_TIMEOUT,
    CONF_CONVERSATION_AGENT,
    CONF_TELEGRAM_ENTRY,
    CONF_TELEGRAM_SUBENTRY,
    CONF_USER,
)


TELEGRAM_CONVERSATION_TIMEOUT = timedelta(hours=24)

_LOGGER = logging.getLogger(__name__)


async def send_message(
    hass: HomeAssistant,
    chat_id: int,
    message_thread_id: int,
    message: str,
    telegram_entry_id: str,
    context: Context | None = None,
    data: dict[str, Any] | None = None,
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

            chunk_messages = await send_message(
                hass,
                chat_id,
                message_thread_id,
                message[:i],
                telegram_entry_id,
                context,
                data,
            )
            message = message[i:]
            messages["chats"].extend(chunk_messages["chats"])

        if len(message) > 0:
            chunk_messages = await send_message(
                hass,
                chat_id,
                message_thread_id,
                message,
                telegram_entry_id,
                context,
                data,
            )
            messages["chats"].extend(chunk_messages["chats"])

        return messages

    if data is None:
        data = {}
    try:
        # First try: markdownv2
        return await hass.services.async_call(
            TELEGRAM_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                **data,
                ATTR_MESSAGE: markdownify(message),
                ATTR_TARGET: chat_id,
                ATTR_MESSAGE_THREAD_ID: message_thread_id,
                CONF_CONFIG_ENTRY_ID: telegram_entry_id,
                ATTR_PARSER: "markdownv2",
            },
            blocking=True,
            context=context,
            return_response=True,
        )
    except HomeAssistantError as err:
        _LOGGER.debug("MarkdownV2 failed: %s", err)
        pass

    try:
        # Second try: markdown
        return await hass.services.async_call(
            TELEGRAM_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                **data,
                ATTR_MESSAGE: message,
                ATTR_TARGET: chat_id,
                ATTR_MESSAGE_THREAD_ID: message_thread_id,
                CONF_CONFIG_ENTRY_ID: telegram_entry_id,
                ATTR_PARSER: "markdown",
            },
            blocking=True,
            context=context,
            return_response=True,
        )
    except HomeAssistantError as err:
        _LOGGER.debug("Markdown failed: %s", err)
        pass

    # Third try: plain_text
    return await hass.services.async_call(
        TELEGRAM_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            **data,
            ATTR_MESSAGE: message,
            ATTR_TARGET: chat_id,
            ATTR_MESSAGE_THREAD_ID: message_thread_id,
            CONF_CONFIG_ENTRY_ID: telegram_entry_id,
            ATTR_PARSER: "plain_text",
        },
        blocking=True,
        context=context,
        return_response=True,
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""

    telegram_entry_id = entry.data.get(CONF_TELEGRAM_ENTRY)
    telegram_entry = hass.config_entries.async_get_entry(telegram_entry_id)

    # TODO: Check if a telegram subentry has been deleted and raise a repair issue

    telegram_id_map = {
        subentry_id: subentry.data[CONF_CHAT_ID]
        for subentry_id, subentry in telegram_entry.subentries.items()
        if subentry.subentry_type == SUBENTRY_TYPE_ALLOWED_CHAT_IDS
        and subentry.data.get(CONF_CHAT_ID) is not None
        and subentry.subentry_id
        in [
            s.data[CONF_TELEGRAM_SUBENTRY]
            for s in entry.subentries.values()
            if s.subentry_type == "telegram_id"
        ]
    }

    user_id_map = {
        telegram_id_map[subentry.data[CONF_TELEGRAM_SUBENTRY]]: subentry.data[CONF_USER]
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "telegram_id"
        and subentry.data.get(CONF_USER) is not None
        and subentry.data.get(CONF_TELEGRAM_SUBENTRY) in telegram_id_map
    }

    agent_id_map = {
        telegram_id_map[subentry.data[CONF_TELEGRAM_SUBENTRY]]: subentry.data.get(
            CONF_CONVERSATION_AGENT
        )
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "telegram_id"
        and subentry.data.get(CONF_USER) is not None
        and subentry.data.get(CONF_TELEGRAM_SUBENTRY) in telegram_id_map
    }

    subentry_id_map = {
        telegram_id_map[subentry.data[CONF_TELEGRAM_SUBENTRY]]: subentry_id
        for subentry_id, subentry in entry.subentries.items()
        if subentry.subentry_type == "telegram_id"
        and subentry.data.get(CONF_TELEGRAM_SUBENTRY) in telegram_id_map
    }

    async def text_events(event: Event):
        conversation_id = f"telegram_{event.data[ATTR_CHAT_ID]}"
        if event.data.get(ATTR_MESSAGE_THREAD_ID) is not None:
            conversation_id += f"_{event.data[ATTR_MESSAGE_THREAD_ID]}"
        context = event.context
        if context.user_id is None:
            context.user_id = user_id_map.get(
                event.data[ATTR_USER_ID], user_id_map.get(event.data[ATTR_CHAT_ID])
            )

        await hass.services.async_call(
            TELEGRAM_DOMAIN,
            SERVICE_SEND_CHAT_ACTION,
            {
                CONF_CONFIG_ENTRY_ID: telegram_entry_id,
                ATTR_TARGET: event.data[ATTR_CHAT_ID],
                ATTR_MESSAGE_THREAD_ID: event.data.get(ATTR_MESSAGE_THREAD_ID) or 0,
                ATTR_CHAT_ACTION: CHAT_ACTION_TYPING,
            },
            context=context,
        )

        current_delta = ""
        current_role = None

        @callback
        def chat_log_delta_listener(chat_log: ChatLog, delta: dict) -> None:
            """Handle chat log delta."""
            _LOGGER.debug("Chat log delta: %s", delta)
            nonlocal current_delta, current_role
            if "role" in delta:
                if current_role == "assistant" and current_delta:
                    hass.async_create_task(
                        send_message(
                            hass,
                            chat_id=event.data[ATTR_CHAT_ID],
                            message_thread_id=event.data.get(ATTR_MESSAGE_THREAD_ID)
                            or 0,
                            message=current_delta,
                            telegram_entry_id=telegram_entry_id,
                            context=context,
                        )
                    )
                current_delta = ""
                current_role = delta["role"]
            if "content" in delta and current_role == "assistant":
                current_delta += delta["content"]

        with (
            async_get_chat_session(hass, conversation_id) as session,
            async_get_chat_log(
                hass, session, chat_log_delta_listener=chat_log_delta_listener
            ) as chat_log,
        ):
            conversation_result = await async_converse(
                hass,
                text=event.data[ATTR_TEXT],
                conversation_id=session.conversation_id,
                context=context,
                agent_id=agent_id_map.get(event.data[ATTR_CHAT_ID]),
            )
            # Flush any remaining delta
            chat_log_delta_listener(chat_log, {"role": None})

        timeout = entry.options.get(
            CONF_CONVERSATION_TIMEOUT,
            {"seconds": TELEGRAM_CONVERSATION_TIMEOUT.total_seconds()},
        )
        session.last_updated = (
            dt_util.utcnow() + timedelta(**timeout) - CONVERSATION_TIMEOUT
        )

        if conversation_result.response.response_type == IntentResponseType.ERROR:
            await send_message(
                hass,
                chat_id=event.data[ATTR_CHAT_ID],
                message_thread_id=event.data.get(ATTR_MESSAGE_THREAD_ID) or 0,
                message=conversation_result.response.speech["plain"]["speech"],
                telegram_entry_id=telegram_entry_id,
                context=context,
            )

    @callback
    def text_events_filter(event_data: dict[str, Any]) -> bool:
        return (
            event_data.get("bot", {}).get(CONF_CONFIG_ENTRY_ID) == telegram_entry_id
            and event_data.get(ATTR_CHAT_ID) in telegram_id_map.values()
            and event_data.get(ATTR_CHAT_ID) == event_data.get(ATTR_USER_ID)
        )

    entry.async_on_unload(hass.bus.async_listen(EVENT_TELEGRAM_TEXT, text_events, text_events_filter))

    async def _change_agent(chat_id: int, agent_id: str) -> bool:
        _LOGGER.debug("Change agent for chat_id=%s to agent_id=%s", chat_id, agent_id)
        if chat_id not in telegram_id_map.values():
            return False

        agent_id_map[chat_id] = agent_id
        subentry = entry.subentries.get(subentry_id_map[chat_id])
        data = {**subentry.data, CONF_CONVERSATION_AGENT: agent_id}
        _LOGGER.debug("Updating subentry %s with data %s", subentry.subentry_id, data)
        try:
            hass.config_entries.async_update_subentry(entry, subentry, data=data)
        except Exception as e:
            _LOGGER.exception(
                "Failed to update subentry %s: %s",
                subentry.subentry_id,
                e,
                stack_info=True,
            )
            return False
        _LOGGER.debug("Subentry %s updated", subentry.subentry_id)

        return True

    async def process_command(
        chat_id, message_thread_id, command, args, context
    ) -> None:
        _LOGGER.debug("Received command: %s with args: %s", command, args)
        match command:
            case "/model":
                selected_agent = args[0] if len(args) > 0 else None
                current_agent = agent_id_map.get(chat_id)

                agents = {
                    agent.id: agent.name
                    for agent in get_agent_manager(hass).async_get_agent_info()
                    if not isinstance(
                        get_agent_manager(hass).async_get_agent(agent.id),
                        ConversationEntity,
                    )
                } | {
                    entity.entity_id: (
                        hass.states.get(entity.entity_id).name
                        if hass.states.get(entity.entity_id)
                        else entity.entity_id
                    )
                    for entity in hass.data[DATA_COMPONENT].entities
                }

                _LOGGER.debug(
                    "Selected agent: %s, current agent: %s, available agents: %s",
                    selected_agent,
                    current_agent,
                    agents,
                )
                if (
                    selected_agent is not None
                    and selected_agent in agents
                    and chat_id in subentry_id_map
                    and await _change_agent(chat_id, selected_agent)
                ):
                    _LOGGER.debug(
                        "Agent switched to %s for chat_id=%s",
                        selected_agent,
                        chat_id,
                    )
                    await send_message(
                        hass,
                        chat_id=chat_id,
                        message_thread_id=message_thread_id,
                        message=f"Conversation agent switched to `{agents.get(selected_agent, selected_agent)}`",
                        telegram_entry_id=telegram_entry_id,
                        context=context,
                    )
                else:
                    await send_message(
                        hass,
                        chat_id=chat_id,
                        message_thread_id=message_thread_id,
                        message=f"Current conversation agent: `{agents.get(current_agent, current_agent)}`",
                        telegram_entry_id=telegram_entry_id,
                        context=context,
                        data={
                            ATTR_KEYBOARD_INLINE: [
                                [(agent_name, f"/model {agent_id}")]
                                for agent_id, agent_name in agents.items()
                            ]
                        },
                    )

    async def command_events(event: Event):
        context = event.context
        if context.user_id is None:
            context.user_id = user_id_map.get(
                event.data[ATTR_USER_ID], user_id_map.get(event.data[ATTR_CHAT_ID])
            )
        try:
            await process_command(
                event.data[ATTR_CHAT_ID],
                event.data.get(ATTR_MESSAGE_THREAD_ID) or 0,
                event.data.get("command"),
                event.data.get("args", []),
                context,
            )
        except Exception as e:
            _LOGGER.exception("Failed to process command: %s", e, stack_info=True)

    @callback
    def command_events_filter(event_data: dict[str, Any]) -> bool:
        return (
            event_data.get("command") in ["/model"]
            and event_data.get("bot", {}).get(CONF_CONFIG_ENTRY_ID) == telegram_entry_id
            and event_data.get(ATTR_CHAT_ID) in telegram_id_map.values()
            and event_data.get(ATTR_CHAT_ID) == event_data.get(ATTR_USER_ID)
        )

    entry.async_on_unload(hass.bus.async_listen(EVENT_TELEGRAM_COMMAND, command_events, command_events_filter))

    async def callback_events(event: Event):
        _LOGGER.debug("callback_event data: %s", event.data)
        context = event.context
        if context.user_id is None:
            context.user_id = user_id_map.get(
                event.data[ATTR_USER_ID], user_id_map.get(event.data[ATTR_CHAT_ID])
            )
        args = event.data.get("data", "").split(" ")

        try:
            await process_command(
                event.data[ATTR_CHAT_ID],
                event.data.get(ATTR_MESSAGE, {}).get(ATTR_MESSAGE_THREAD_ID) or 0,
                args.pop(0),
                args,
                context,
            )
            await hass.services.async_call(
                TELEGRAM_DOMAIN,
                SERVICE_ANSWER_CALLBACK_QUERY,
                {
                    CONF_CONFIG_ENTRY_ID: telegram_entry_id,
                    ATTR_MESSAGE: "Done",
                    ATTR_CALLBACK_QUERY_ID: event.data.get("id"),
                },
                context=context,
            )

        except Exception as e:
            _LOGGER.exception("Failed to process command: %s", e, stack_info=True)
        return

    @callback
    def callback_events_filter(event_data: dict[str, Any]) -> bool:
        return (
            event_data.get("data").startswith("/model")
            and event_data.get("bot", {}).get(CONF_CONFIG_ENTRY_ID) == telegram_entry_id
            and event_data.get(ATTR_CHAT_ID) in telegram_id_map.values()
            and event_data.get(ATTR_CHAT_ID) == event_data.get(ATTR_USER_ID)
        )

    entry.async_on_unload(hass.bus.async_listen(
        EVENT_TELEGRAM_CALLBACK, callback_events, callback_events_filter
    ))

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Telegram Bot Conversation."""
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)
