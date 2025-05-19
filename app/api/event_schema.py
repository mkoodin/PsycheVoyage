from pydantic import BaseModel
from typing import Optional, List, Dict, Any

"""
Event Schema Module

This module defines the Pydantic models that FastAPI uses to validate incoming
HTTP requests. It specifies the expected structure and validation rules for
events entering the system through the API endpoints.
"""


class DiscordUser(BaseModel):
    id: int
    username: str
    discriminator: str
    avatar: Optional[str]
    bot: Optional[bool] = False
    system: Optional[bool] = False


class DiscordAttachment(BaseModel):
    id: int
    filename: str
    size: int
    url: str
    proxy_url: Optional[str]
    height: Optional[int]
    width: Optional[int]
    content_type: Optional[str]


class DiscordEmbedAuthor(BaseModel):
    name: Optional[str]
    url: Optional[str]
    icon_url: Optional[str]


class DiscordEmbedFooter(BaseModel):
    text: str
    icon_url: Optional[str]


class DiscordEmbedField(BaseModel):
    name: str
    value: str
    inline: Optional[bool] = False


class DiscordEmbed(BaseModel):
    title: Optional[str]
    type: Optional[str] = "rich"
    description: Optional[str]
    url: Optional[str]
    timestamp: Optional[str]
    color: Optional[int]
    footer: Optional[DiscordEmbedFooter]
    author: Optional[DiscordEmbedAuthor]
    fields: Optional[List[DiscordEmbedField]]


class DiscordReaction(BaseModel):
    emoji: Dict[str, Any]  # Contains "name", "id", and "animated"
    count: int
    me: bool


class DiscordSticker(BaseModel):
    id: int
    name: str
    format_type: int  # 1 = PNG, 2 = APNG, 3 = LOTTIE


class EventSchema(BaseModel):
    id: int
    channel_id: int
    guild_id: Optional[int]
    content: str
    author: DiscordUser
    timestamp: str
    edited_timestamp: Optional[str]
    mentions: List[DiscordUser]
    mention_roles: List[int]
    mention_everyone: bool
    attachments: List[DiscordAttachment]
    embeds: List[DiscordEmbed]
    reactions: Optional[List[DiscordReaction]]
    pinned: bool
    type: int  # Discord message type (0 = Default, 1 = Recipient Add, etc.)
    webhook_id: Optional[int]
    stickers: Optional[List[DiscordSticker]]
    referenced_message_id: Optional[int]
    referenced_message_author_id: Optional[int]
    referenced_message_author_name: Optional[str]
    referenced_message_content: Optional[str]

    class Config:
        from_attributes = True


# json_data = {
#     "id": 1340782013967237282,
#     "channel_id": 1339870218100543550,
#     "guild_id": 1339870217488306249,
#     "content": "<@1339861530430406657> what is wellness",
#     "author": {
#         "id": 988733900509548605,
#         "username": "datamonkey.eth",
#         "discriminator": "0",
#         "avatar": "https://cdn.discordapp.com/avatars/988733900509548605/0ebeb088d0f47949380c5a51180a4c74.png?size=1024",
#         "bot": False,
#         "system": False
#     },
#     "timestamp": "2025-02-16 20:29:02.655000+00:00",
#     "edited_timestamp": None,
#     "mentions": [
#         {
#             "id": 1339861530430406657,
#             "username": "PsycheVoyageBot",
#             "discriminator": "2729",
#             "avatar": None,
#             "bot": True,
#             "system": False
#         }
#     ],
#     "mention_roles": [],
#     "mention_everyone": False,
#     "attachments": [],
#     "embeds": [],
#     "reactions": [],
#     "pinned": False,
#     "type": 0,
#     "webhook_id": None,
#     "stickers": [],
#     "referenced_message_id": None,
#     "referenced_message_author_id": None,
#     "referenced_message_author_name": None,
#     "referenced_message_content": None
# }

# event = EventSchema(**json_data)
