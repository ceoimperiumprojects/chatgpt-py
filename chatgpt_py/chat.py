"""Backward compatibility — re-exports from modules.chat."""
from .modules.chat import (
    send_message,
    wait_for_response,
    ask,
    ask_stream,
    continue_chat,
    new_chat,
    regenerate,
    stop_generating,
    edit_message,
    get_chat_messages,
)
