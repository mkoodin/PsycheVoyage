from core.pipeline import Pipeline
from core.schema import PipelineSchema, NodeConfig
from pipelines.message.analyze_message import AnalyzeMessage
from pipelines.message.generate_response import GenerateResponse

# from pipelines.message.route_message import MessageRouter
# from pipelines.message.wellness_response import WellnessResponse
from pipelines.message.send_reply import SendReply


"""
Psyche Voyage Discord Messages Pipeline
This pipeline handles messages sent in the Psyche Voyage Discord server
"""


class MessagePipeline(Pipeline):
    pipeline_schema = PipelineSchema(
        description="Pipeline for messages to Psyche Voyage Discord server",
        start=AnalyzeMessage,
        nodes=[
            NodeConfig(
                node=AnalyzeMessage,
                connections=[GenerateResponse],
                description="Analyze the incoming user message and pass it to the next node",
            ),
            NodeConfig(
                node=GenerateResponse,
                connections=[SendReply],
                description="Generate a response to the Discord message",
            ),
            NodeConfig(
                node=SendReply,
                connections=[],
                description="Send a reply to the Discord message",
            ),
        ],
    )
