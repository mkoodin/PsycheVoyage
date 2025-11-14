from enum import Enum
from core.task import TaskContext
from core.llm import LLMNode
from services.prompt_loader import PromptManager
from pydantic import BaseModel, Field
from services.llm_factory import LLMFactory
from api.event_schema import DiscordUser
from typing import List, Optional, Any
from dotenv import load_dotenv
from sqlalchemy import select, desc
from database.session import SessionLocal
from database.event import Event
from sqlalchemy import String


class MessageIntent(str, Enum):
    PLATFORM_BUSINESS_INFO = "platform and business info"
    PERSONAL_GROWTH_CREATIVITY = "personal growth and creativity"
    MINDFULNESS = "mindfulness"
    BREATHWORK = "breathwork"
    HYPNOSIS = "hypnosis"
    TRAUMA_SOMATIC_THERAPY = "trauma and somatic therapy"
    IGNORE = "ignore"

    @property
    def escalate(self) -> bool:
        # Define escalation rules if needed
        return False


class AnalyzeMessage(LLMNode):
    class ContextModel(BaseModel):
        content: str
        author: DiscordUser
        timestamp: str
        mentions: List[DiscordUser]
        referenced_message_id: Optional[int]
        referenced_message_author_id: Optional[int]
        referenced_message_author_name: Optional[str]
        referenced_message_content: Optional[str]
        channel_id: str

    class ResponseModel(BaseModel):
        reasoning: str = Field(
            description="Explain the reasoning behind the intent classification"
        )
        intent: MessageIntent
        confidence: float = Field(
            ge=0, le=1, description="Confidence score for the intent classification"
        )
        escalate: bool = Field(
            description="Flag to indicate if the message requires escalation"
        )

    def get_context(self, task_context: TaskContext) -> ContextModel:
        return self.ContextModel(
            content=task_context.event.content,
            author=task_context.event.author,
            timestamp=task_context.event.timestamp,
            mentions=task_context.event.mentions,
            referenced_message_id=task_context.event.referenced_message_id
            if task_context.event.referenced_message_id
            else None,
            referenced_message_author_id=task_context.event.referenced_message_author_id
            if task_context.event.referenced_message_author_id
            else None,
            referenced_message_author_name=task_context.event.referenced_message_author_name
            if task_context.event.referenced_message_author_name
            else None,
            referenced_message_content=task_context.event.referenced_message_content
            if task_context.event.referenced_message_content
            else None,
            channel_id=str(task_context.event.channel_id),
        )

    def get_conversation_history(self, channel_id: str, limit: int = 10) -> List[dict]:
        """
        Fetch the last N messages from the events table for the given channel.

        Args:
            channel_id: The Discord channel ID
            limit: Number of previous messages to fetch (default: 10)

        Returns:
            List of previous messages with their details, matching ContextModel structure
        """
        with SessionLocal() as db:
            # Query to get the last N messages from the channel
            stmt = (
                select(Event)
                .where(Event.data["channel_id"].cast(String) == str(channel_id))
                .order_by(desc(Event.created_at))
                .limit(limit)
            )
            results = db.execute(stmt).scalars().all()

            # Convert to list of dicts with relevant information
            history = []
            for event in results:
                message_data = event.data
                if not message_data:
                    continue

                history.append(
                    {
                        "content": message_data.get("content"),
                        "author": message_data.get(
                            "author"
                        ),  # Already matches DiscordUser format
                        "timestamp": message_data.get("timestamp"),
                        "mentions": message_data.get("mentions", []),
                        "referenced_message_id": message_data.get(
                            "referenced_message_id"
                        ),
                        "referenced_message_author_id": message_data.get(
                            "referenced_message_author_id"
                        ),
                        "referenced_message_author_name": message_data.get(
                            "referenced_message_author_name"
                        ),
                        "referenced_message_content": message_data.get(
                            "referenced_message_content"
                        ),
                        "channel_id": message_data.get("channel_id"),
                    }
                )

            return history[::-1]  # Reverse to get chronological order

    def create_completion(self, context: ContextModel) -> tuple[ResponseModel, Any]:
        # # Check if bot is mentioned or referenced
        # bot_mentioned = any(user.id == 1339861530430406657 for user in context.mentions)
        # bot_referenced = context.referenced_message_author_id == 1339861530430406657

        # # If bot is NOT mentioned and NOT referenced, set intent to IGNORE
        # if not bot_mentioned and not bot_referenced:
        #     response = self.ResponseModel(
        #         reasoning="The bot was neither mentioned nor referenced in the message, so it is ignored.",
        #         intent=MessageIntent.IGNORE,
        #         confidence=1.0,
        #         escalate=False,
        #     )
        #     # Return a tuple with None as completion since we didn't use LLM
        #     return response, None

        # Check if message is from the bot
        if context.author.id == 1339861530430406657:  # Bot ID
            response = self.ResponseModel(
                reasoning="The message is from the bot itself, so it is ignored.",
                intent=MessageIntent.IGNORE,
                confidence=1.0,
                escalate=False,
            )
            return response, None

        # Get conversation history
        channel_id = context.channel_id
        history = self.get_conversation_history(channel_id)

        # Otherwise, proceed with normal LLM classification
        llm = LLMFactory("openai")
        prompt = PromptManager.get_prompt(
            "message_analysis",
            pipeline="message",
        )
        return llm.create_completion(
            response_model=self.ResponseModel,
            messages=[
                {
                    "role": "system",
                    "content": prompt,
                },
                {
                    "role": "user",
                    "content": f"# Conversation History:\n{history}\n\n# New message:\n{context.model_dump()}",
                },
            ],
        )

    def process(self, task_context: TaskContext) -> TaskContext:
        context = self.get_context(task_context)
        response_model, completion = self.create_completion(context)
        task_context.nodes[self.node_name] = {
            "response_model": response_model,
            "usage": completion.usage if completion is not None else None,
        }
        return task_context
