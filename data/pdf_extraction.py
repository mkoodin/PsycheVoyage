from typing import List
from docling.chunking import HybridChunker
from docling.document_converter import DocumentConverter
from dotenv import load_dotenv
from openai import OpenAI
from utils.tokenizer import OpenAITokenizerWrapper
import os

dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)

# Initialize OpenAI client (make sure you have OPENAI_API_KEY in your environment variables)
client = OpenAI()


tokenizer = OpenAITokenizerWrapper()  # Load our custom tokenizer for OpenAI
MAX_TOKENS = 8191  # text-embedding-3-large's maximum context length

# --------------------------------------------------------------
# Extract the data
# --------------------------------------------------------------

converter = DocumentConverter()

result = converter.convert("On_Becoming_A_Person.pdf")

# --------------------------------------------------------------
# Apply hybrid chunking and save as JSON
# --------------------------------------------------------------

chunker = HybridChunker(
    tokenizer=tokenizer,
    max_tokens=MAX_TOKENS,
    merge_peers=True,
)

chunk_iter = chunker.chunk(dl_doc=result.document)
chunks = list(chunk_iter)

chunks_edit = [
    {
        "source": "On Becoming A Person",
        "author": "Carl Rogers",
        "category": "breathwork",
        "text": item.text,
        "headings": getattr(item.meta, "headings"),
    }
    for item in chunks
]

import json

with open("On_Becoming_A_Person.json", "w", encoding="utf-8") as f:
    json.dump(chunks_edit, f, ensure_ascii=False, indent=4)


# chunks_edit[]['headings']

# chunks[1]

# chunks[9].text
# chunks[9].headings


# chunks[6].model_dump()

# chunks[1]["text"]

# .model_dump()
