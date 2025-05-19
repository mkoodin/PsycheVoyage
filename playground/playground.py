import os
import sys
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root / "app"))

os.environ["DATABASE_HOST"] = "localhost"

# Load environment variables
load_dotenv(project_root / "app" / ".env")
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

if not DISCORD_TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN not found in environment variables")

from utils.event_factory import EventFactory
from pipelines.registry import PipelineRegistry
from services.discord_bot import get_discord_bot

"""
This playground is used to test the PipelineRegistry and the pipelines themselves.
"""

# Initialize the Discord bot with token in test mode
discord_bot = get_discord_bot(DISCORD_TOKEN, test_mode=True)

# Create the event
event = EventFactory.create_event("message")
pipeline = PipelineRegistry.get_pipeline(event)

# Run the pipeline
output = pipeline.run(event)

output.nodes["AnalyzeMessage"]

# Print the output for inspection
print("\nPipeline Output:")
print("---------------")
for node_name, node_data in output.nodes.items():
    print(f"\n{node_name}:")
    print(node_data)
