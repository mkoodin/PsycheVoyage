import discord
import asyncio
from discord.ext import commands
import threading
import logging
from typing import Optional
import time
import os
from dotenv import load_dotenv
import requests

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class DiscordBot:
    def __init__(self, command_prefix: str, token: str):
        logger.debug("Initializing DiscordBot")
        intents = discord.Intents.default()
        intents.messages = True
        intents.guilds = True
        intents.message_content = True

        self.token = token
        self.is_ready = False
        self.is_connected = False
        self.test_mode = False
        self._lock = threading.Lock()
        self._ready_event = threading.Event()
        self._connected_event = threading.Event()

        # Use Docker service name and port for API URL
        default_api_url = "http://api:8080"
        self.api_url = os.getenv("API_URL", default_api_url)
        logger.info(f"Using API URL: {self.api_url}")

        # Create the actual bot instance
        self.bot = commands.Bot(command_prefix=command_prefix, intents=intents)
        logger.info("DiscordBot initialized with intents")

        # Register event handlers
        self.setup_events()

    def setup_events(self):
        """Setup event handlers for connection status tracking"""

        @self.bot.event
        async def on_connect():
            logger.info("Bot connected to Discord")
            self.is_connected = True
            self._connected_event.set()

        @self.bot.event
        async def on_disconnect():
            logger.warning("Bot disconnected from Discord")
            self.is_connected = False
            self._connected_event.clear()

        @self.bot.event
        async def on_ready():
            logger.info(f"Logged in as {self.bot.user}")
            self.is_ready = True
            self._ready_event.set()

        @self.bot.event
        async def on_error(event, *args, **kwargs):
            logger.error(f"Discord event error in {event}", exc_info=True)

    def get_channel(self, channel_id: int):
        """Get a channel by ID"""
        return self.bot.get_channel(channel_id)

    async def fetch_channel(self, channel_id: int):
        """Fetch a channel by ID using the API"""
        try:
            return await self.bot.fetch_channel(channel_id)
        except Exception as e:
            logger.error(f"Error fetching channel {channel_id}: {str(e)}")
            return None

    async def send_message(self, channel_id: int, message: str):
        """Send a message to a specific channel."""
        logger.debug(f"Attempting to send message to channel {channel_id}")
        if self.test_mode:
            logger.info(
                f"TEST MODE: Would send message to channel {channel_id}: {message}"
            )
            return

        # Try fetch_channel first, then fall back to get_channel
        channel = await self.fetch_channel(channel_id)
        if not channel:
            channel = self.get_channel(channel_id)

        if channel:
            await channel.send(message)
            logger.debug(f"Message sent to channel {channel_id}")
        else:
            error_msg = f"Channel {channel_id} not found"
            logger.error(error_msg)
            raise ValueError(error_msg)

    def wait_for_ready(self, timeout_seconds: int = 60) -> bool:
        """Wait for the bot to be ready with a timeout."""
        return self._ready_event.wait(timeout=timeout_seconds)

    def wait_for_connected(self, timeout_seconds: int = 60) -> bool:
        """Wait for the bot to be connected with a timeout."""
        return self._connected_event.wait(timeout=timeout_seconds)

    def send_message_sync(self, channel_id: int, message: str):
        """
        Synchronous version of send_message that uses the bot directly.
        """
        if self.test_mode:
            logger.info(
                f"TEST MODE: Would send message to channel {channel_id}: {message}"
            )
            return True

        logger.debug(f"Attempting to send message to channel {channel_id}")
        try:
            # Initialize event loop if needed
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # If bot is not ready, start it
            if not self.is_ready:
                logger.info("Bot not ready, starting it...")

                # Run the bot in a separate thread to avoid blocking
                def start_bot():
                    loop.run_until_complete(self.bot.start(self.token))

                bot_thread = threading.Thread(target=start_bot)
                bot_thread.daemon = True
                bot_thread.start()

                # Wait for bot to be ready
                if not self.wait_for_ready(timeout_seconds=30):
                    raise RuntimeError("Bot failed to start and become ready")

            # Try to fetch the channel using the API
            async def get_and_send():
                try:
                    # Use fetch_channel instead of get_channel
                    logger.info(f"Fetching channel {channel_id}")
                    channel = await self.bot.fetch_channel(channel_id)

                    if not channel:
                        # Fall back to get_channel if fetch_channel fails
                        logger.warning(
                            f"fetch_channel failed, trying get_channel for {channel_id}"
                        )
                        channel = self.get_channel(channel_id)

                    if channel:
                        logger.info(f"Channel found: {channel.name} (ID: {channel.id})")
                        await channel.send(message)
                        logger.info(f"Message sent to channel {channel_id}")
                        return True
                    else:
                        error_msg = f"Channel {channel_id} not found"
                        logger.error(error_msg)
                        raise ValueError(error_msg)
                except Exception as e:
                    logger.error(f"Error in get_and_send: {str(e)}")
                    raise

            # Create and run the coroutine in the bot's event loop
            future = asyncio.run_coroutine_threadsafe(get_and_send(), self.bot.loop)
            result = future.result(timeout=30)  # Wait for the message to be sent
            return result

        except Exception as e:
            error_msg = f"Failed to send message: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

    async def run_bot(self):
        """Run the bot using asyncio."""
        logger.info("Starting bot")
        if not self.test_mode:
            try:
                self.start_time = time.time()
                logger.info("Starting bot connection")

                # Get or create event loop
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                # Set up heartbeat monitoring
                self.bot.heartbeat_timeout = 150.0  # Increase heartbeat timeout

                # Start the bot
                await self.bot.start(self.token)
            except discord.LoginFailure as e:
                logger.error(f"Failed to login: Invalid token or permissions: {str(e)}")
                raise
            except Exception as e:
                logger.error(f"Error running bot: {str(e)}", exc_info=True)
                raise
            finally:
                if not self.bot.is_closed():
                    await self.bot.close()

    def enable_test_mode(self):
        """Enable test mode to prevent actual Discord API calls."""
        logger.info("Enabling test mode")
        self.test_mode = True
        self.is_ready = True
        self.is_connected = True
        self._ready_event.set()
        self._connected_event.set()


# Singleton instance
_discord_bot = None


def get_discord_bot(token: str = None, test_mode: bool = False) -> DiscordBot:
    logger.debug("Getting Discord bot instance")
    global _discord_bot
    if _discord_bot is None:
        if token is None:
            error_msg = "Token is required when creating a new Discord bot instance"
            logger.error(error_msg)
            raise ValueError(error_msg)
        logger.info("Creating new Discord bot instance")
        _discord_bot = DiscordBot(command_prefix="!", token=token)
        if test_mode:
            _discord_bot.enable_test_mode()
    return _discord_bot
