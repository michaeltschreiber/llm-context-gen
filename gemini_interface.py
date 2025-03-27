# gemini_interface.py

import google.generativeai as genai
import logging
from typing import Tuple, Optional
import sys
import os
from gemini_api_key import GEMINI_API_KEY

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---
# Use the specific model requested by the user, verified as existing on 2025-03-27
MODEL_NAME = "gemini-2.5-pro-exp-03-25"

# Max characters for context snippet sent to Gemini for analysis
CONTEXT_SNIPPET_MAX_CHARS = 10000000000 # Keep this relatively small to avoid large API calls just for persona generation

# Attempt to import the API key - Add current dir to path temporarily if needed
try:
    # Ensure the directory containing GEMINI_API_KEY.py is in the Python path
    sys.path.insert(0, os.path.dirname(__file__))

    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set or is placeholder in GEMINI_API_KEY.py")
    # Remove the path modification after import (optional, depends on project structure)
    # sys.path.pop(0)
except ImportError:
    GEMINI_API_KEY = None
    logger.error("GEMINI_API_KEY.py not found.")
except Exception as e:
    GEMINI_API_KEY = None
    logger.error(f"Error importing GEMINI_API_KEY: {e}")


# --- Core Function ---

def generate_expert_system_prompt(full_context: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Uses the specified Gemini model to generate a system prompt suggesting an expert persona
    based on a snippet of the provided context.

    Args:
        full_context: The entire generated context string (XML format).

    Returns:
        A tuple containing:
        - The generated system prompt (str) or None if an error occurred.
        - An error message (str) or None if successful.
    """
    if not GEMINI_API_KEY:
        return None, "Configuration Error: GEMINI_API_KEY not found, empty, or placeholder in GEMINI_API_KEY.py"

    if not full_context or not full_context.strip():
         return None, "Input Error: Input context is empty."

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        logger.info("Google AI SDK configured successfully.")
    except Exception as e:
        logger.error(f"Failed to configure Google AI SDK: {e}", exc_info=True)
        return None, f"API Config Error: {e}"

    # Create a representative snippet
    context_snippet = full_context.strip()[:CONTEXT_SNIPPET_MAX_CHARS]
    if len(full_context.strip()) > CONTEXT_SNIPPET_MAX_CHARS:
         context_snippet += "\n[... context truncated ...]" # Clearer indication

    # Define the prompt for Gemini to generate the system prompt
    meta_prompt = f"""Analyze the following text snippet extracted from a larger context document (formatted with XML tags like <document path="...">). Identify the primary subject matter, domain, or key technologies discussed.

Based on this analysis, generate a concise system prompt (4-8 sentences) suitable for another AI assistant. This system prompt should:
1. Instruct the assistant to adopt the persona of a knowledgeable expert in the identified domain/subject (e.g., "You are an expert Python developer specializing in data analysis libraries...").
2. Emphasize using the *full context* (which will be provided to the assistant separately) to answer questions accurately, comprehensively, and based on the provided documents preferentially. Empasize use of search tool to verify facts or extend knowledge.
3. Guide the assistant to cite the source document path when possible or relevant.
4. Avoid mentioning the snippet analysis process in the final output.

Output *only* the generated system prompt text, with no extra explanations, preamble, or formatting like markdown quotes.

Snippet:
-------
{context_snippet}
-------
Generated System Prompt:"""

    try:
        logger.info(f"Generating system prompt using model: {MODEL_NAME}...")
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(
            meta_prompt,
            generation_config=genai.types.GenerationConfig(
                # candidate_count=1, # Default is 1
                # stop_sequences=['...'],
                # max_output_tokens=250, # Limit output tokens slightly more
                temperature=0.7 # Slightly lower temperature for more focused persona prompt
            ),
            # Optional: Add safety settings if defaults are too strict/lenient
             safety_settings={
                 # Example: Block fewer things (use with caution)
                 # 'HATE': 'BLOCK_ONLY_HIGH',
                 # 'HARASSMENT': 'BLOCK_ONLY_HIGH',
             }
            )

        # More robust checking of response content
        if hasattr(response, 'text'):
            generated_prompt = response.text.strip()
            if not generated_prompt: # Check if the text itself is empty
                 # Check for block reason if text is empty
                 if response.prompt_feedback.block_reason:
                     block_reason = response.prompt_feedback.block_reason.name
                     logger.warning(f"Generation blocked. Reason: {block_reason}")
                     return None, f"Content generation blocked due to safety filters ({block_reason})."
                 else:
                     logger.warning("Generation response text was empty.")
                     return None, "Error: Received an empty text response from the AI model."
            logger.info("Successfully generated system prompt suggestion.")
            return generated_prompt, None # Success
        elif response.prompt_feedback.block_reason:
             block_reason = response.prompt_feedback.block_reason.name
             logger.warning(f"Generation blocked (no text attribute). Reason: {block_reason}")
             return None, f"Content generation blocked ({block_reason})."
        else:
             # If no text and no block reason, it's an unexpected state
             logger.error(f"Unexpected response structure: {response}")
             return None, "Error: Unexpected response structure from the AI model."


    except Exception as e:
        logger.error(f"Error during Google AI API call with model '{MODEL_NAME}': {e}", exc_info=True)
        err_str = str(e).lower()
        if "api key not valid" in err_str:
             return None, "API Error: Invalid Google AI API Key. Please check GEMINI_API_KEY.py."
        elif "quota" in err_str:
             return None, "API Error: Quota exceeded. Check Google Cloud limits or try later."
        elif "model" in err_str and ("not found" in err_str or "permission" in err_str):
             return None, f"API Error: Model '{MODEL_NAME}' not found or permission denied. Check model name and API key access."
        else:
            # Generic error for other cases
            return None, f"API Error: {e}"