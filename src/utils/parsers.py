import json
import re
from json_repair import repair_json


def load_json_from_llm_result(text):
    """
    Extract and clean JSON from markdown code blocks.
    Returns the first valid JSON found or None if no valid JSON is found.
    """
    # First, try to find JSON blocks
    pattern = r"```(?:json)?\s*([\s\S]*)```"
    matches = re.findall(pattern, text, re.DOTALL)
    if not matches:
        return None
    # Process each potential JSON block
    for json_text in matches:
    
        good_json_string = repair_json(json_text)
        # Try to parse the JSON to verify it's valid
        try:
            return json.loads(good_json_string)
        except json.JSONDecodeError:
            continue
    # If we've tried all matches and none are valid JSON, return None
    return None