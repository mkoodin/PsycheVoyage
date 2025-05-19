from celery import shared_task
from wellness_content_manager import WellnessContentManager
import logging

logger = logging.getLogger(__name__)


@shared_task
def generate_and_post_wellness_content():
    """
    Celery task to generate and post wellness content to Discord.
    This task will be scheduled to run every 10 minutes.
    """
    try:
        manager = WellnessContentManager()
        result = manager.generate_and_post()

        if result["success"]:
            logger.info(
                f"Successfully generated and posted {result['content_type']} content (ID: {result['content_id']})"
            )
        else:
            logger.error(
                f"Failed to generate and post content: {result['error_message']}"
            )

        return result
    except Exception as e:
        logger.error(
            f"Error in generate_and_post_wellness_content task: {str(e)}", exc_info=True
        )
        return {"success": False, "error_message": str(e)}
