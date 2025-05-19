import os
import asyncio
import logging
import discord
import aiohttp
from dotenv import load_dotenv
from fastapi import FastAPI
from contextlib import asynccontextmanager
from api.router import router as process_router
from services.discord_bot import get_discord_bot
from api.event_schema import (
    EventSchema,
    DiscordUser,
    DiscordAttachment,
    DiscordEmbed,
    DiscordEmbedFooter,
    DiscordEmbedAuthor,
    DiscordEmbedField,
    DiscordReaction,
    DiscordSticker,
)

BASE_URL = "http://localhost:8080/events"

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get Discord Bot instance
bot = get_discord_bot(TOKEN)

# Create aiohttp session
session = None


@bot.bot.event
async def on_ready():
    global session
    session = aiohttp.ClientSession()
    logger.info(f"Logged in as {bot.bot.user.name}#{bot.bot.user.discriminator}")


@bot.bot.event
async def on_message(message):
    try:
        # Process commands first
        await bot.bot.process_commands(message)

        # Try to fetch referenced message
        referenced_message = None
        if message.reference:
            try:
                referenced_message = await message.channel.fetch_message(
                    message.reference.message_id
                )
            except discord.NotFound:
                logger.warning("Referenced message not found.")
            except discord.Forbidden:
                logger.warning("Bot lacks permissions to fetch the message.")
            except discord.HTTPException as e:
                logger.error(f"Failed to fetch message: {e}")

        # Construct message event schema
        msg_data = EventSchema(
            id=message.id,
            channel_id=message.channel.id,
            guild_id=message.guild.id if message.guild else None,
            content=message.content,
            author=DiscordUser(
                id=message.author.id,
                username=message.author.name,
                discriminator=message.author.discriminator,
                avatar=message.author.avatar.url if message.author.avatar else None,
                bot=message.author.bot,
            ),
            timestamp=str(message.created_at),
            edited_timestamp=str(message.edited_at) if message.edited_at else None,
            mentions=[
                DiscordUser(
                    id=user.id,
                    username=user.name,
                    discriminator=user.discriminator,
                    avatar=user.avatar.url if user.avatar else None,
                    bot=user.bot,
                )
                for user in message.mentions
            ],
            mention_roles=[role.id for role in message.role_mentions],
            mention_everyone=message.mention_everyone,
            attachments=[
                DiscordAttachment(
                    id=att.id,
                    filename=att.filename,
                    size=att.size,
                    url=att.url,
                    proxy_url=att.proxy_url,
                    height=att.height,
                    width=att.width,
                    content_type=att.content_type,
                )
                for att in message.attachments
            ],
            embeds=[
                DiscordEmbed(
                    title=embed.title,
                    type=embed.type,
                    description=embed.description,
                    url=embed.url,
                    timestamp=str(embed.timestamp) if embed.timestamp else None,
                    color=embed.color,
                    footer=DiscordEmbedFooter(
                        text=embed.footer.text, icon_url=embed.footer.icon_url
                    )
                    if embed.footer
                    else None,
                    author=DiscordEmbedAuthor(
                        name=embed.author.name,
                        url=embed.author.url,
                        icon_url=embed.author.icon_url,
                    )
                    if embed.author
                    else None,
                    fields=[
                        DiscordEmbedField(
                            name=field.name,
                            value=field.value,
                            inline=field.inline,
                        )
                        for field in embed.fields
                    ]
                    if embed.fields
                    else [],
                )
                for embed in message.embeds
            ],
            reactions=[
                DiscordReaction(
                    emoji={
                        "name": reaction.emoji.name,
                        "id": reaction.emoji.id,
                        "animated": reaction.emoji.animated,
                    },
                    count=reaction.count,
                    me=reaction.me,
                )
                for reaction in message.reactions
            ]
            if message.reactions
            else [],
            pinned=message.pinned,
            type=message.type.value,
            webhook_id=message.webhook_id,
            stickers=[
                DiscordSticker(
                    id=sticker.id, name=sticker.name, format_type=sticker.format_type
                )
                for sticker in message.stickers
            ]
            if message.stickers
            else [],
            referenced_message_id=referenced_message.id if referenced_message else None,
            referenced_message_author_id=referenced_message.author.id
            if referenced_message
            else None,
            referenced_message_author_name=referenced_message.author.name
            if referenced_message
            else None,
            referenced_message_content=referenced_message.content
            if referenced_message
            else None,
        )

        try:
            # Use aiohttp for async HTTP request with timeout
            async with session.post(
                BASE_URL, json=msg_data.model_dump(), timeout=5
            ) as response:
                if response.status not in [
                    200,
                    202,
                ]:  # Accept both 200 and 202 as success
                    logger.error(f"API returned status code: {response.status}")
                    await message.channel.send(
                        "Sorry, I encountered an error processing your message."
                    )
        except asyncio.TimeoutError:
            logger.error("API request timed out")
            await message.channel.send(
                "Sorry, the request timed out while processing your message."
            )
        except aiohttp.ClientError as e:
            logger.error(f"API request failed: {e}")
            await message.channel.send(
                "Sorry, I encountered an error processing your message."
            )

    except Exception as e:
        logger.error(f"Error in on_message event: {e}")
        await message.channel.send(
            "An unexpected error occurred while processing your message."
        )


@bot.bot.event
async def on_close():
    if session:
        await session.close()


async def run_discord_bot():
    """Runs the Discord bot."""
    try:
        await bot.run_bot()
    except Exception as e:
        logger.error(f"Discord bot crashed: {e}")
        raise


# Lifespan function to manage startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup and shutdown of the FastAPI app."""
    # Get the current event loop
    loop = asyncio.get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Start the Discord bot in the background
    bot_task = loop.create_task(run_discord_bot())

    yield

    # Cleanup
    bot_task.cancel()
    try:
        await bot_task
    except asyncio.CancelledError:
        pass
    if not bot.bot.is_closed():
        await bot.bot.close()


# Create FastAPI app
app = FastAPI(lifespan=lifespan)

# Include the process router
app.include_router(process_router)
