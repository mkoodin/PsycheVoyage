from core.llm import LLMNode
from services.prompt_loader import PromptManager
from pydantic import BaseModel, Field
from core.task import TaskContext
from services.llm_factory import LLMFactory
from services.vector_store import VectorStore
from api.event_schema import DiscordUser
from typing import List, Optional
from sqlalchemy import select, desc, String
from database.session import SessionLocal
from database.event import Event


class GenerateResponse(LLMNode):
    """
    A node to generate a response for a Discord message.

    This class inherits from LLMNode and implements the necessary methods
    to process a customer ticket and generate a response using RAG.

    Attributes:
        vector_store (VectorStore): An instance of VectorStore for semantic search.
    """

    class ContextModel(BaseModel):
        content: str
        author: DiscordUser
        timestamp: str
        mentions: List[DiscordUser]
        referenced_message_id: Optional[int]
        referenced_message_author_id: Optional[int]
        referenced_message_author_name: Optional[str]
        referenced_message_content: Optional[str]
        intent: str
        channel_id: str

    class ResponseModel(BaseModel):
        reasoning: str = Field(description="The reasoning for the response")
        response: str = Field(description="The response to the ticket")
        confidence: float = Field(
            ge=0, le=1, description="Confidence score for how helpful the response is"
        )

    def __init__(self):
        super().__init__()
        self.vector_store = VectorStore()

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
            intent=task_context.nodes["AnalyzeMessage"]["response_model"].intent,
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

    def search_kb(self, query: str, intent: str) -> list[str]:
        results = self.vector_store.semantic_search(
            query=query,
            limit=10,
            metadata_filter={"category": intent},
            return_dataframe=True,
        )
        return results["contents"].tolist()

    def create_completion(
        self, context: ContextModel
    ) -> tuple[ResponseModel, list[str]]:
        # Get conversation history
        history = self.get_conversation_history(context.channel_id)

        # Get RAG context
        rag_context = self.search_kb(context.content, context.intent)

        llm = LLMFactory("openai")
        SYSTEM_PROMPT = PromptManager.get_prompt(template="message_response")
        response_model, completion = llm.create_completion(
            response_model=self.ResponseModel,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": f"# Conversation History:\n{history}\n\n# New message:\n{context.model_dump()}\n\n# Retrieved information:\n{rag_context}",
                },
            ],
        )
        return response_model, completion, rag_context

    def process(self, task_context: TaskContext) -> TaskContext:
        context = self.get_context(task_context)
        response_model, completion, rag_context = self.create_completion(context)
        task_context.nodes[self.node_name] = {
            "response_model": response_model,
            "rag_context": rag_context,
            "usage": completion.usage,
        }
        return task_context
