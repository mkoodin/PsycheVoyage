import json
import os
from pathlib import Path
from typing import List, Union


def combine_json_files(
    input_dir: str, output_file: str, recursive: bool = False
) -> None:
    """
    Combine multiple JSON files into a single JSON file.

    Args:
        input_dir (str): Directory containing JSON files to combine
        output_file (str): Path to the output JSON file
        recursive (bool): Whether to search for JSON files recursively in subdirectories
    """
    combined_data = []

    # Convert input directory to Path object
    input_path = Path(input_dir)

    # Get all JSON files
    pattern = "**/*.json" if recursive else "*.json"
    json_files = list(input_path.glob(pattern))

    if not json_files:
        print(f"No JSON files found in {input_dir}")
        return

    # Read and combine all JSON files
    for json_file in json_files:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Handle both single objects and arrays
                if isinstance(data, list):
                    combined_data.extend(data)
                else:
                    combined_data.append(data)
        except json.JSONDecodeError as e:
            print(f"Error reading {json_file}: {e}")
        except Exception as e:
            print(f"Unexpected error with {json_file}: {e}")

    # Write combined data to output file
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(combined_data, f, indent=4)
        print(f"Successfully combined {len(json_files)} JSON files into {output_file}")
    except Exception as e:
        print(f"Error writing to output file: {e}")


if __name__ == "__main__":
    # Example usage
    input_directory = "./"  # Directory containing JSON files
    output_file = "dataset.json"  # Output file name

    # Create the input directory if it doesn't exist
    os.makedirs(input_directory, exist_ok=True)

    # Combine JSON files
    combine_json_files(input_directory, output_file, recursive=False)
