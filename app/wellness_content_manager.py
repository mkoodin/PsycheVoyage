# python scripts/test_wellness_content_manager_db.py --action both --content_type "sleep optimization"
# python scripts/test_wellness_content_manager_db.py --action both

import os
import logging
import time
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Import required services
from services.llm_factory import LLMFactory
from services.prompt_loader import PromptManager
from services.discord_bot import get_discord_bot

# Import database modules conditionally to handle testing without a database
try:
    from sqlalchemy import select, desc
    from database.session import SessionLocal
    from database.wellness_content import WellnessContent

    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
except Exception as e:
    logging.error(f"Error importing database modules: {str(e)}")
    DATABASE_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Mock database for testing
mock_content_store = []
mock_content_id_counter = 1


class ContentType(str, Enum):
    """Types of wellness content that can be generated"""

    MEDITATION_TIP = "meditation tip"
    WEEKLY_CHALLENGE = "weekly challenge"
    MINDFULNESS_PRACTICE = "mindfulness practice"
    EMOTIONAL_WELLNESS = "emotional wellness"
    SOMATIC_EXERCISE = "somatic exercise"
    BREATHWORK_TECHNIQUE = "breathwork technique"
    SLEEP_OPTIMIZATION = "sleep optimization"
    GRATITUDE_PRACTICE = "gratitude practice"
    BOUNDARY_SETTING = "boundary setting"
    STRESS_MANAGEMENT = "stress management"


class ContentContext(BaseModel):
    """Context model for wellness content generation"""

    day_of_week: str
    content_type: ContentType
    previous_content: List[str]
    channel_id: str


class ContentResponse(BaseModel):
    """Response model for wellness content generation"""

    reasoning: str = Field(description="The reasoning behind the content generation")
    content: str = Field(description="The generated wellness content")
    confidence: float = Field(
        ge=0, le=1, description="Confidence score for the quality of the content"
    )


class GeneratedContent(BaseModel):
    """Model for the generated content and metadata"""

    content: str
    content_type: str
    channel_id: str
    generated_at: datetime
    reasoning: Optional[str] = None
    confidence: Optional[float] = None
    id: Optional[str] = None


class PostResult(BaseModel):
    """Result of posting content to Discord"""

    success: bool
    error_message: Optional[str] = None
    channel_id: str
    content_id: Optional[str] = None
    posted_at: Optional[datetime] = None


class WellnessContentManager:
    """
    A class to generate and send wellness-related content for Discord posts.

    This class combines the functionality of GenerateContent and SendWellnessContent
    into a single manager that can handle the entire process from generation to posting.
    """

    def __init__(self):
        """Initialize the WellnessContentManager with required components."""
        logger.info("Initializing WellnessContentManager")

        # Initialize Discord bot if token is available
        token = os.getenv("DISCORD_BOT_TOKEN")
        self.discord_bot = None

        if token:
            try:
                logger.debug("Attempting to initialize Discord bot")
                self.discord_bot = get_discord_bot(token=token)
                logger.info("Discord bot initialized successfully")
            except Exception as e:
                logger.error(
                    f"Failed to initialize Discord bot: {str(e)}", exc_info=True
                )
                # Continue without Discord bot - we'll check before sending

    def get_previous_content(
        self, channel_id: str, limit: int = 100
    ) -> List[Tuple[str, str, datetime]]:
        """
        Fetch the last N content posts from the database for the given channel.

        Args:
            channel_id: The Discord channel ID
            limit: Number of previous content posts to fetch (default: 100)

        Returns:
            List of tuples containing (content, content_type, updated_at)
        """
        previous_content = []

        with SessionLocal() as db:
            # First, check the wellness_content table for posted content
            stmt = (
                select(WellnessContent)
                .where(WellnessContent.channel_id == channel_id)
                .where(WellnessContent.posted == True)  # Only get posted content
                .order_by(
                    desc(WellnessContent.updated_at)
                )  # Order by most recently updated
                .limit(limit)
            )

            results = db.execute(stmt).scalars().all()

            # Extract content, type, and updated_at from the results
            for item in results:
                if item.content:
                    previous_content.append(
                        (item.content, item.content_type, item.updated_at)
                    )

            # If we don't have enough content, also check other channels
            if len(previous_content) < limit:
                try:
                    # Get content from any channel that has been posted
                    stmt = (
                        select(WellnessContent)
                        .where(
                            WellnessContent.posted == True
                        )  # Only get posted content
                        .order_by(desc(WellnessContent.updated_at))
                        .limit(limit - len(previous_content))
                    )

                    results = db.execute(stmt).scalars().all()

                    # Extract content from the results
                    for item in results:
                        if (
                            item.content
                            and (item.content, item.content_type, item.updated_at)
                            not in previous_content
                        ):
                            previous_content.append(
                                (item.content, item.content_type, item.updated_at)
                            )
                except Exception as e:
                    logger.warning(f"Error querying additional content: {str(e)}")
                    # Continue with what we have

        logger.info(
            f"Retrieved {len(previous_content)} previous content items for channel {channel_id}"
        )
        return previous_content

    def determine_content_type(
        self, previous_content: List[Tuple[str, str, datetime]]
    ) -> ContentType:
        """
        Determine the next content type based on rotation and previous content.

        Args:
            previous_content: List of tuples containing (content, content_type, updated_at)

        Returns:
            ContentType for the next post
        """
        # Default to a random content type if no previous content
        if not previous_content:
            logger.info("No previous content found, using default content type")
            return ContentType.MEDITATION_TIP

        # Get the most recent content type (already sorted by updated_at)
        last_content = previous_content[0]
        last_type_str = last_content[1]  # Get the content_type string

        # Find the matching enum value
        try:
            last_type = None
            for content_type in ContentType:
                if content_type.value == last_type_str:
                    last_type = content_type
                    break

            if last_type:
                # Get the next type in rotation
                all_types = list(ContentType)
                current_index = all_types.index(last_type)
                next_index = (current_index + 1) % len(all_types)
                next_type = all_types[next_index]
                logger.info(
                    f"Rotating content type from {last_type.value} to {next_type.value}"
                )
                return next_type
            else:
                logger.warning(f"Could not match content type: {last_type_str}")
                return ContentType.MEDITATION_TIP

        except Exception as e:
            logger.error(f"Error determining next content type: {str(e)}")
            return ContentType.MEDITATION_TIP

    def prepare_context(
        self, channel_id: Optional[str] = None, content_type: Optional[str] = None
    ) -> ContentContext:
        """
        Prepares context data for the language model.

        Args:
            channel_id: Optional channel ID to use
            content_type: Optional content type to use

        Returns:
            ContentContext containing prepared data for the LLM
        """
        # Get the day of the week
        day_of_week = datetime.now().strftime("%A")

        # Use provided channel ID or get from environment
        if not channel_id:
            channel_id = os.getenv("WELLNESS_CHANNEL_ID", "0")
            logger.info(f"Using channel ID from environment: {channel_id}")

        # Get previous content for the channel
        previous_content_data = self.get_previous_content(channel_id)
        previous_content = [content for content, _, _ in previous_content_data]

        # Use provided content type or determine based on rotation
        if content_type and content_type in [ct.value for ct in ContentType]:
            # Find the matching enum value
            for ct in ContentType:
                if ct.value == content_type:
                    selected_content_type = ct
                    break
            logger.info(f"Using provided content type: {content_type}")
        else:
            # Determine content type based on rotation
            selected_content_type = self.determine_content_type(previous_content_data)

        logger.info(
            f"Prepared context for {selected_content_type.value} content on {day_of_week}"
        )

        return ContentContext(
            day_of_week=day_of_week,
            content_type=selected_content_type,
            previous_content=previous_content,
            channel_id=channel_id,
        )

    def create_completion(self, context: ContentContext) -> Tuple[ContentResponse, Any]:
        """
        Creates a completion using the language model.

        Args:
            context: Prepared context data conforming to ContentContext

        Returns:
            Tuple containing ContentResponse and completion metadata
        """
        logger.info(f"Creating completion for {context.content_type.value} content")

        llm = LLMFactory("openai")

        # Get the prompt template with required variables
        try:
            SYSTEM_PROMPT = PromptManager.get_prompt(
                template="wellness_content",
                day_of_week=context.day_of_week,
                content_type=context.content_type.value,
                previous_content=context.previous_content,
            )
        except Exception as e:
            # Fallback to a simpler approach if template rendering fails
            logger.warning(f"Error rendering prompt template: {str(e)}")
            SYSTEM_PROMPT = PromptManager.get_prompt(template="wellness_content")

        # Create the completion
        response_model, completion = llm.create_completion(
            response_model=ContentResponse,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": f"""# Context:
Day of Week: {context.day_of_week}
Content Type: {context.content_type.value}

# Previous Content (for reference to ensure uniqueness):
{context.previous_content if context.previous_content else "No previous content available"}
""",
                },
            ],
        )

        logger.info("Successfully generated wellness content")
        return response_model, completion

    def store_content(
        self,
        content: str,
        content_type: str,
        channel_id: str,
        reasoning: str = None,
        confidence: float = None,
    ) -> str:
        """
        Store the generated content in the database.

        Args:
            content: The generated wellness content
            content_type: The type of wellness content
            channel_id: The Discord channel ID
            reasoning: The reasoning behind the generated content
            confidence: Confidence score for the quality of the content

        Returns:
            The ID of the stored content
        """
        # Use mock database if real database is not available
        if not DATABASE_AVAILABLE:
            global mock_content_id_counter
            content_id = str(mock_content_id_counter)
            mock_content_id_counter += 1

            mock_content_store.append(
                {
                    "id": content_id,
                    "content": content,
                    "content_type": content_type,
                    "channel_id": channel_id,
                    "posted": False,
                    "reasoning": reasoning,
                    "confidence": confidence,
                    "created_at": datetime.utcnow(),
                }
            )

            logger.info(
                f"Stored wellness content with ID {content_id} in mock database"
            )
            return content_id

        try:
            with SessionLocal() as db:
                wellness_content = WellnessContent(
                    content=content,
                    content_type=content_type,
                    channel_id=channel_id,
                    posted=False,
                    reasoning=reasoning,
                    confidence=confidence,
                )

                db.add(wellness_content)
                db.commit()
                db.refresh(wellness_content)

                logger.info(f"Stored wellness content with ID {wellness_content.id}")
                return str(wellness_content.id)
        except Exception as e:
            logger.error(f"Error storing content in database: {str(e)}")
            # Fall back to mock storage if database fails
            return self.store_content_mock(
                content, content_type, channel_id, reasoning, confidence
            )

    def store_content_mock(
        self,
        content: str,
        content_type: str,
        channel_id: str,
        reasoning: str = None,
        confidence: float = None,
    ) -> str:
        """Mock implementation for storing content when database is unavailable"""
        global mock_content_id_counter
        content_id = str(mock_content_id_counter)
        mock_content_id_counter += 1

        mock_content_store.append(
            {
                "id": content_id,
                "content": content,
                "content_type": content_type,
                "channel_id": channel_id,
                "posted": False,
                "reasoning": reasoning,
                "confidence": confidence,
                "created_at": datetime.utcnow(),
            }
        )

        logger.info(
            f"Stored wellness content with ID {content_id} in mock database (fallback)"
        )
        return content_id

    def generate_content(
        self, channel_id: Optional[str] = None, content_type: Optional[str] = None
    ) -> GeneratedContent:
        """
        Generate wellness content.

        Args:
            channel_id: Optional channel ID to use
            content_type: Optional content type to use

        Returns:
            GeneratedContent object with the generated content and metadata
        """
        logger.info("Generating wellness content")

        # Prepare context
        context = self.prepare_context(channel_id, content_type)

        # Generate content
        response_model, completion = self.create_completion(context)

        # Store the generated content in the database
        content_id = self.store_content(
            content=response_model.content,
            content_type=context.content_type.value,
            channel_id=context.channel_id,
            reasoning=response_model.reasoning,
            confidence=response_model.confidence,
        )

        # Create and return the generated content object
        generated_content = GeneratedContent(
            content=response_model.content,
            content_type=context.content_type.value,
            channel_id=context.channel_id,
            generated_at=datetime.utcnow(),
            reasoning=response_model.reasoning,
            confidence=response_model.confidence,
            id=content_id,
        )

        logger.info(
            f"Generated {context.content_type.value} content and stored in database with ID {content_id}"
        )
        return generated_content

    def update_content_posted_status(
        self, content_id: str, posted: bool, posted_at: Optional[datetime] = None
    ) -> bool:
        """
        Update the posted status of wellness content in the database.

        Args:
            content_id: The ID of the content to update
            posted: Whether the content was posted
            posted_at: When the content was posted

        Returns:
            True if the update was successful, False otherwise
        """
        # Use mock database if real database is not available
        if not DATABASE_AVAILABLE:
            for item in mock_content_store:
                if item.get("id") == content_id:
                    item["posted"] = posted
                    if posted and posted_at:
                        item["posted_at"] = posted_at
                    logger.info(
                        f"Updated posted status for content ID {content_id} to {posted} in mock database"
                    )
                    return True
            logger.warning(f"Content with ID {content_id} not found in mock database")
            return False

        try:
            with SessionLocal() as db:
                # Find the content by ID
                content = (
                    db.query(WellnessContent)
                    .filter(WellnessContent.id == content_id)
                    .first()
                )

                if not content:
                    logger.warning(
                        f"Content with ID {content_id} not found in database"
                    )
                    return False

                # Update the posted status
                content.posted = posted
                if posted and posted_at:
                    content.posted_at = posted_at

                # Commit the changes
                db.commit()
                logger.info(
                    f"Updated posted status for content ID {content_id} to {posted}"
                )
                return True
        except Exception as e:
            logger.error(f"Error updating posted status: {str(e)}", exc_info=True)
            # Try mock update as fallback
            return self.update_content_posted_status_mock(content_id, posted, posted_at)

    def update_content_posted_status_mock(
        self, content_id: str, posted: bool, posted_at: Optional[datetime] = None
    ) -> bool:
        """Mock implementation for updating content status when database is unavailable"""
        for item in mock_content_store:
            if item.get("id") == content_id:
                item["posted"] = posted
                if posted and posted_at:
                    item["posted_at"] = posted_at
                logger.info(
                    f"Updated posted status for content ID {content_id} to {posted} in mock database (fallback)"
                )
                return True
        logger.warning(
            f"Content with ID {content_id} not found in mock database (fallback)"
        )
        return False

    def post_content(
        self,
        content: str,
        channel_id: Optional[str] = None,
        content_id: Optional[str] = None,
    ) -> PostResult:
        """
        Post wellness content to Discord.

        Args:
            content: The wellness content to post
            channel_id: The Discord channel ID to post to
            content_id: Optional ID of the content in the database

        Returns:
            PostResult object with the result of the posting operation
        """
        logger.debug("Starting post_content method")
        try:
            # Validate content
            if not content or not content.strip():
                error_msg = "Empty content received"
                logger.warning(error_msg)
                return PostResult(
                    success=False,
                    error_message=error_msg,
                    channel_id=channel_id or "unknown",
                )

            # Use provided channel ID or get from environment
            if not channel_id:
                channel_id = os.getenv("WELLNESS_CHANNEL_ID")
                if not channel_id:
                    error_msg = (
                        "Channel ID not found in parameters or environment variables"
                    )
                    logger.error(error_msg)
                    return PostResult(
                        success=False, error_message=error_msg, channel_id="unknown"
                    )

            logger.debug(f"Posting wellness content to channel {channel_id}")
            logger.debug(f"Content: {content[:100]}...")  # Log first 100 chars
            logger.debug(f"Content length: {len(content)}")

            # Check if Discord bot is initialized
            logger.debug("Checking Discord bot initialization")
            if not self.discord_bot:
                error_msg = "Discord bot not initialized"
                logger.error(error_msg)
                return PostResult(
                    success=False, error_message=error_msg, channel_id=channel_id
                )

            # Send the message with retries
            max_retries = 3
            retry_delay = 1  # seconds
            last_error = None

            for attempt in range(max_retries):
                try:
                    logger.debug(f"Attempt {attempt + 1} to send wellness content")

                    # Use the synchronous version of send_message
                    logger.debug("Calling send_message_sync")
                    self.discord_bot.send_message_sync(int(channel_id), content)
                    logger.debug("Wellness content sent successfully")

                    # Update the database if content_id is provided
                    posted_at = datetime.utcnow()
                    if content_id:
                        self.update_content_posted_status(content_id, True, posted_at)

                    logger.info(
                        f"Successfully sent wellness content to channel {channel_id} on attempt {attempt + 1}"
                    )

                    return PostResult(
                        success=True,
                        channel_id=channel_id,
                        content_id=content_id,
                        posted_at=posted_at,
                    )
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
            error_msg = f"Failed to send wellness content after {max_retries} attempts. Last error: {last_error}"
            logger.error(error_msg)
            return PostResult(
                success=False,
                error_message=error_msg,
                channel_id=channel_id,
                content_id=content_id,
            )

        except Exception as e:
            error_msg = f"Error in post_content method: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return PostResult(
                success=False,
                error_message=error_msg,
                channel_id=channel_id or "unknown",
                content_id=content_id,
            )

    def generate_and_post(
        self, channel_id: Optional[str] = None, content_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate wellness content and post it to Discord in one operation.

        Args:
            channel_id: Optional channel ID to use
            content_type: Optional content type to use

        Returns:
            Dictionary with results of the operation
        """
        logger.info("Starting generate and post operation")

        try:
            # Generate content
            generated_content = self.generate_content(channel_id, content_type)

            # Post the content
            post_result = self.post_content(
                content=generated_content.content,
                channel_id=generated_content.channel_id,
                content_id=generated_content.id,
            )

            # Return combined results
            return {
                "success": post_result.success,
                "content": generated_content.content,
                "content_type": generated_content.content_type,
                "channel_id": generated_content.channel_id,
                "content_id": generated_content.id,
                "generated_at": generated_content.generated_at,
                "posted_at": post_result.posted_at if post_result.success else None,
                "error_message": post_result.error_message,
                "reasoning": generated_content.reasoning,
                "confidence": generated_content.confidence,
            }
        except Exception as e:
            error_msg = f"Error in generate_and_post: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "error_message": error_msg,
                "channel_id": channel_id or os.getenv("WELLNESS_CHANNEL_ID", "unknown"),
            }


# Example usage
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate and post wellness content to Discord"
    )
    parser.add_argument("--channel", help="Discord channel ID to post to")
    parser.add_argument("--type", help="Type of wellness content to generate")
    parser.add_argument(
        "--generate-only", action="store_true", help="Only generate content, don't post"
    )
    args = parser.parse_args()

    manager = WellnessContentManager()

    if args.generate_only:
        # Only generate content
        content = manager.generate_content(args.channel, args.type)
        print(f"Generated {content.content_type} content (ID: {content.id}):")
        print(content.content)
    else:
        # Generate and post
        result = manager.generate_and_post(args.channel, args.type)
        if result["success"]:
            print(
                f"Successfully generated and posted {result['content_type']} content (ID: {result['content_id']})"
            )
            print(result["content"])
        else:
            print(f"Error: {result['error_message']}")
