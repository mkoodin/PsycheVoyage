from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker
from utils.sitemap import get_sitemap_urls
import json
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

# Initialize the document converter
converter = DocumentConverter()

# Initialize the hybrid chunker with a suitable embedding model
chunker = HybridChunker(
    tokenizer=tokenizer,
    max_tokens=MAX_TOKENS,
    merge_peers=True,
)


def serialize_metadata(meta):
    """Convert metadata object to a serializable dictionary."""
    if hasattr(meta, "__dict__"):
        return {
            key: (
                serialize_metadata(value)
                if hasattr(value, "__dict__")
                else value
                if isinstance(value, list)
                else str(value)
            )
            for key, value in meta.__dict__.items()
            if not key.startswith("_")
        }
    return str(meta) if not isinstance(meta, list) else meta


# Scrape multiple pages using the sitemap and chunk them
# --------------------------------------------------------------

sitemap_urls = get_sitemap_urls("https://psychevoyage.com/")
conv_results_iter = converter.convert_all(sitemap_urls)
all_chunks = []

for result in conv_results_iter:
    if result.document:
        document = result.document
        # Process each document with hybrid chunking
        chunk_iter = chunker.chunk(dl_doc=document)

        # Get the serialized chunks with metadata
        for chunk in chunk_iter:
            # Extract headings from metadata
            meta_dict = serialize_metadata(chunk.meta)
            headings = (
                meta_dict.get("headings", []) if isinstance(meta_dict, dict) else []
            )

            all_chunks.append(
                {
                    "source": "psychevoyage.com",
                    "author": "psychevoyage",
                    "category": "platform and business info",
                    "text": chunk.text,
                    "headings": headings,
                }
            )

# Deduplicate chunks based on text content
seen_texts = set()
deduplicated_chunks = []

for chunk in all_chunks:
    if chunk["text"] not in seen_texts:
        seen_texts.add(chunk["text"])
        deduplicated_chunks.append(chunk)

print(f"Removed {len(all_chunks) - len(deduplicated_chunks)} duplicate chunks")
all_chunks = deduplicated_chunks

# Save the chunks to a file
with open("website_data.json", "w", encoding="utf-8") as f:
    json.dump(all_chunks, f, indent=2, ensure_ascii=False)
