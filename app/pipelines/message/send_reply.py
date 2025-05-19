import os
from dotenv import load_dotenv
from core.task import TaskContext
from core.base import Node
from pydantic import BaseModel
from services.discord_bot import get_discord_bot, DiscordBot
import logging
from typing import Optional
import asyncio
import time

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class SendReply(Node):
    """
    A node to send responses back to Discord channels.
    This is the final node in the message pipeline that takes the generated response
    and sends it back to the appropriate Discord channel.
    """

    def __init__(self):
        """Initialize the SendReply node with a Discord bot instance."""
        super().__init__()
        logger.debug("Initializing SendReply node")
        token = os.getenv("DISCORD_BOT_TOKEN")
        if not token:
            logger.error("Discord bot token not found in environment variables")
            raise ValueError("Discord bot token not found in environment variables")
        try:
            logger.debug("Attempting to initialize Discord bot")
            self.discord_bot = get_discord_bot(token=token)
            logger.info("Discord bot initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Discord bot: {str(e)}", exc_info=True)
            raise

    class ResponseModel(BaseModel):
        success: bool
        error_message: Optional[str] = None
        channel_id: Optional[int] = None
        message_sent: Optional[str] = None

    def process(self, task_context: TaskContext) -> TaskContext:
        """
        Process the task by sending the generated response to Discord.
        """
        logger.debug("Starting process in SendReply node")
        try:
            logger.debug("Checking for required nodes in context")
            # Check if we have the required nodes in the context
            if "AnalyzeMessage" not in task_context.nodes:
                raise ValueError(
                    "AnalyzeMessage node results not found in task context"
                )
            if "GenerateResponse" not in task_context.nodes:
                raise ValueError(
                    "GenerateResponse node results not found in task context"
                )

            # Check if the intent is IGNORE
            logger.debug("Checking message intent")
            intent = task_context.nodes["AnalyzeMessage"]["response_model"].intent
            if intent == "ignore":
                logger.info("Message intent is IGNORE, skipping reply")
                task_context.nodes[self.node_name] = {
                    "response_model": self.ResponseModel(
                        success=True, error_message="Message ignored as per intent"
                    )
                }
                return task_context

            # Get the channel ID and response from the task context
            logger.debug("Extracting channel ID and response from context")
            channel_id = task_context.event.channel_id
            response = task_context.nodes["GenerateResponse"]["response_model"].response

            if not response or not response.strip():
                logger.warning("Empty response received from GenerateResponse node")
                task_context.nodes[self.node_name] = {
                    "response_model": self.ResponseModel(
                        success=False, error_message="Empty response received"
                    )
                }
                return task_context

            logger.debug(f"Processing message for channel {channel_id}")
            logger.debug(
                f"Response content: {response[:100]}..."
            )  # Log first 100 chars
            logger.debug(f"Response length: {len(response)}")

            # Check if Discord bot is initialized
            logger.debug("Checking Discord bot initialization")
            if not self.discord_bot:
                error_msg = "Discord bot not initialized"
                logger.error(error_msg)
                task_context.nodes[self.node_name] = {
                    "response_model": self.ResponseModel(
                        success=False, error_message=error_msg
                    )
                }
                return task_context

            # Send the message with retries
            max_retries = 3
            retry_delay = 1  # seconds
            last_error = None

            for attempt in range(max_retries):
                try:
                    logger.debug(f"Attempt {attempt + 1} to send message")

                    # Use the synchronous version of send_message
                    logger.debug("Calling send_message_sync")
                    self.discord_bot.send_message_sync(channel_id, response)
                    logger.debug("Message sent successfully")

                    response_model = self.ResponseModel(
                        success=True, channel_id=channel_id, message_sent=response
                    )
                    task_context.nodes[self.node_name] = {
                        "response_model": response_model
                    }
                    logger.info(
                        f"Successfully sent message to channel {channel_id} on attempt {attempt + 1}"
                    )
                    return task_context
                except Exception as e:
                    last_error = str(e)
                    logger.warning(
                        f"Error on attempt {attempt + 1}: {last_error}", exc_info=True
                    )
                    if attempt < max_retries - 1:
                        logger.info(f"Waiting {retry_delay} seconds before retry...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff

            # If we get here, all retries failed
            error_msg = f"Failed to send message after {max_retries} attempts. Last error: {last_error}"
            logger.error(error_msg)
            task_context.nodes[self.node_name] = {
                "response_model": self.ResponseModel(
                    success=False, error_message=error_msg
                )
            }
            return task_context

        except Exception as e:
            error_msg = f"Error in SendReply node: {str(e)}"
            logger.error(error_msg, exc_info=True)
            task_context.nodes[self.node_name] = {
                "response_model": self.ResponseModel(
                    success=False, error_message=error_msg
                )
            }
            return task_context
