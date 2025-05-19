#!/usr/bin/env python
"""
Test Wellness Content Manager Script with Database Connection

This script tests the WellnessContentManager class with a real database connection.
It can test content generation, posting, or both operations.
"""

import sys
import os
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# Override database connection settings for local testing
# Use localhost instead of the Docker container name
os.environ["DATABASE_HOST"] = "localhost"
os.environ["DATABASE_PORT"] = "5432"
os.environ["DATABASE_NAME"] = "psyche-voyage"
os.environ["DATABASE_USER"] = "postgres"
os.environ["DATABASE_PASSWORD"] = "super-secret-postgres-password"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Import the WellnessContentManager
from wellness_content_manager import WellnessContentManager, ContentType
from database.session import SessionLocal
from database.wellness_content import WellnessContent
from sqlalchemy import select, desc


def test_database_connection():
    """Test the database connection."""
    logger.info("Testing database connection...")
    try:
        with SessionLocal() as db:
            # Try a simple query
            result = db.execute(select(1)).scalar()
            if result == 1:
                logger.info("Database connection successful!")
                return True
            else:
                logger.error("Database connection failed: unexpected result")
                return False
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        return False


def list_recent_content(limit=5):
    """List recent wellness content from the database."""
    logger.info(f"Listing {limit} most recent wellness content entries...")
    try:
        with SessionLocal() as db:
            stmt = (
                select(WellnessContent)
                .order_by(desc(WellnessContent.created_at))
                .limit(limit)
            )
            results = db.execute(stmt).scalars().all()

            if not results:
                logger.info("No wellness content found in the database")
                return []

            for i, content in enumerate(results, 1):
                logger.info(f"Content #{i}:")
                logger.info(f"  ID: {content.id}")
                logger.info(f"  Type: {content.content_type}")
                logger.info(f"  Posted: {content.posted}")
                logger.info(f"  Created at: {content.created_at}")
                logger.info(f"  Content preview: {content.content[:50]}...")
                logger.info("---")

            return results
    except Exception as e:
        logger.error(f"Error listing content: {str(e)}")
        return []


def test_generate_content(manager, channel_id=None, content_type=None):
    """Test generating wellness content."""
    logger.info("Testing content generation with WellnessContentManager")

    if channel_id:
        logger.info(f"Channel ID: {channel_id}")
    else:
        channel_id = os.getenv("WELLNESS_CHANNEL_ID")
        logger.info(f"Using default channel ID: {channel_id}")

    if content_type:
        logger.info(f"Content Type: {content_type}")

    # Generate content
    generated_content = manager.generate_content(channel_id, content_type)

    logger.info("\nGenerated content successfully:")
    logger.info(f"Content ID: {generated_content.id}")
    logger.info(f"Content Type: {generated_content.content_type}")
    logger.info(f"Generated at: {generated_content.generated_at}")
    logger.info(f"Content: {generated_content.content[:100]}...")
    logger.info(f"Confidence: {generated_content.confidence}")

    return generated_content


def test_post_content(manager, content, channel_id=None, content_id=None):
    """Test posting wellness content."""
    logger.info("Testing content posting with WellnessContentManager")

    if channel_id:
        logger.info(f"Channel ID: {channel_id}")
    else:
        channel_id = os.getenv("WELLNESS_CHANNEL_ID")
        logger.info(f"Using default channel ID: {channel_id}")

    if content_id:
        logger.info(f"Content ID: {content_id}")

    # Post content
    post_result = manager.post_content(content, channel_id, content_id)

    if post_result.success:
        logger.info(f"Successfully posted content to channel {channel_id}")
        if content_id:
            logger.info(f"Content ID: {content_id}")
        logger.info(f"Posted at: {post_result.posted_at}")
    else:
        logger.error(f"Failed to post content: {post_result.error_message}")

    return post_result


def test_generate_and_post(manager, channel_id=None, content_type=None):
    """Test generating and posting wellness content in one operation."""
    logger.info("Testing combined generation and posting with WellnessContentManager")

    if channel_id:
        logger.info(f"Channel ID: {channel_id}")
    else:
        channel_id = os.getenv("WELLNESS_CHANNEL_ID")
        logger.info(f"Using default channel ID: {channel_id}")

    if content_type:
        logger.info(f"Content Type: {content_type}")

    # Generate and post content
    result = manager.generate_and_post(channel_id, content_type)

    if result["success"]:
        logger.info("\nGenerated and posted content successfully:")
        logger.info(f"Content ID: {result['content_id']}")
        logger.info(f"Content Type: {result['content_type']}")
        logger.info(f"Content: {result['content'][:100]}...")
        logger.info(f"Generated at: {result['generated_at']}")
        logger.info(f"Posted at: {result['posted_at']}")
    else:
        logger.error(f"Failed to generate and post content: {result['error_message']}")

    return result


def test_content_type_rotation(manager):
    """Test the content type rotation functionality."""
    logger.info("Testing content type rotation")

    # Get the default channel ID
    channel_id = os.getenv("WELLNESS_CHANNEL_ID")

    # Get previous content
    previous_content = manager.get_previous_content(channel_id)

    # Determine the next content type
    next_content_type = manager.determine_content_type(previous_content)

    logger.info(f"Next content type in rotation: {next_content_type.value}")

    return next_content_type


def find_unposted_content():
    """Find unposted wellness content in the database."""
    logger.info("Finding unposted wellness content...")
    try:
        with SessionLocal() as db:
            stmt = (
                select(WellnessContent)
                .where(WellnessContent.posted == False)
                .order_by(desc(WellnessContent.created_at))
                .limit(5)
            )
            results = db.execute(stmt).scalars().all()

            if not results:
                logger.info("No unposted wellness content found in the database")
                return None

            for i, content in enumerate(results, 1):
                logger.info(f"Unposted Content #{i}:")
                logger.info(f"  ID: {content.id}")
                logger.info(f"  Type: {content.content_type}")
                logger.info(f"  Created at: {content.created_at}")
                logger.info(f"  Content preview: {content.content[:50]}...")
                logger.info("---")

            # Return the most recent unposted content
            return results[0]
    except Exception as e:
        logger.error(f"Error finding unposted content: {str(e)}")
        return None


def main():
    """Main function to run the test script."""
    parser = argparse.ArgumentParser(
        description="Test the WellnessContentManager with database connection"
    )
    parser.add_argument(
        "--action",
        choices=[
            "generate",
            "post",
            "both",
            "rotation",
            "list",
            "db-test",
            "find-unposted",
        ],
        default="db-test",
        help="Action to perform: generate content, post content, both, test rotation, list recent content, test database connection, or find unposted content",
    )
    parser.add_argument(
        "--channel_id",
        default=None,
        help="Discord channel ID (defaults to WELLNESS_CHANNEL_ID env var)",
    )
    parser.add_argument(
        "--content_type",
        default=None,
        help="Type of content to generate (e.g., 'meditation tip', 'weekly challenge')",
    )
    parser.add_argument(
        "--content",
        default=None,
        help="Content to post (only used with --action=post)",
    )
    parser.add_argument(
        "--content_id",
        default=None,
        help="ID of content to post (only used with --action=post)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Limit for listing content (only used with --action=list)",
    )

    args = parser.parse_args()

    # Test database connection first
    if args.action == "db-test":
        test_database_connection()
        return

    # List recent content
    if args.action == "list":
        list_recent_content(args.limit)
        return

    # Find unposted content
    if args.action == "find-unposted":
        find_unposted_content()
        return

    # Initialize the wellness content manager
    manager = WellnessContentManager()

    if args.action == "generate":
        test_generate_content(manager, args.channel_id, args.content_type)
    elif args.action == "post":
        # If no content is provided but content_id is, try to find the content in the database
        if not args.content and args.content_id:
            try:
                with SessionLocal() as db:
                    content_obj = (
                        db.query(WellnessContent)
                        .filter(WellnessContent.id == args.content_id)
                        .first()
                    )
                    if content_obj:
                        content = content_obj.content
                        logger.info(
                            f"Found content with ID {args.content_id} in the database"
                        )
                        test_post_content(
                            manager, content, args.channel_id, args.content_id
                        )
                    else:
                        logger.error(
                            f"Content with ID {args.content_id} not found in the database"
                        )
            except Exception as e:
                logger.error(f"Error retrieving content from database: {str(e)}")
        elif not args.content:
            # If no content and no content_id, try to find unposted content
            unposted = find_unposted_content()
            if unposted:
                logger.info(f"Using unposted content with ID {unposted.id}")
                test_post_content(
                    manager, unposted.content, args.channel_id, str(unposted.id)
                )
            else:
                logger.error(
                    "No content provided and no unposted content found. Use --content to specify content."
                )
        else:
            test_post_content(manager, args.content, args.channel_id, args.content_id)
    elif args.action == "both":
        test_generate_and_post(manager, args.channel_id, args.content_type)
    elif args.action == "rotation":
        test_content_type_rotation(manager)


if __name__ == "__main__":
    main()
