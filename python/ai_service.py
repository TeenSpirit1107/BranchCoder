#!/usr/bin/env python3
"""
AI Service for VS Code Extension
This script receives messages via stdin and returns AI responses via stdout.
Logs are written to stderr to avoid interfering with JSON output on stdout.
"""

import json
import sys
from typing import List, Dict
from logger import Logger

# Initialize logger (logs to stderr by default, no file logging)
# To enable file logging, set log_to_file=True
logger = Logger('ai_service', log_to_file=False)

def get_ai_response(message: str, history: List[Dict[str, str]]) -> str:
    """
    Process the user message and generate an AI response.
    
    Args:
        message: The current user message
        history: List of previous messages in format [{"role": "user|assistant", "content": "..."}]
    
    Returns:
        The AI response string
    """
    logger.debug(f"Processing AI request - message length: {len(message)}, history length: {len(history)}")
    
    try:
        # TODO: Replace this with your actual AI implementation
        # Example: Using a simple echo response
        # You can integrate your actual AI model here (e.g., OpenAI, local LLM, etc.)
        
        logger.info(f"Generating response for message: {message[:50]}{'...' if len(message) > 50 else ''}")
        
        # Simple example response
        response = f"I received your message: {message}\n\nThis is a placeholder response. " \
                   f"Please integrate your actual AI model in the get_ai_response function."
        
        # Example: If you want to use OpenAI API:
        # import openai
        # response = openai.ChatCompletion.create(
        #     model="gpt-3.5-turbo",
        #     messages=history + [{"role": "user", "content": message}]
        # ).choices[0].message.content
        
        # Example: If you want to use a local model:
        # from transformers import pipeline
        # generator = pipeline("text-generation", model="your-model")
        # response = generator(message, max_length=100)[0]['generated_text']
        
        logger.debug(f"Generated response length: {len(response)}")
        return response
        
    except Exception as e:
        logger.error(f"Error in get_ai_response: {e}", exc_info=True)
        raise

def main():
    """Main entry point - reads from stdin, processes, writes to stdout"""
    try:
        logger.info("AI service started, waiting for input...")
        
        # Read input from stdin
        input_data = sys.stdin.read()
        
        if not input_data:
            logger.error("No input data received")
            raise ValueError("No input data received")
        
        logger.debug(f"Received input data length: {len(input_data)}")
        
        # Parse JSON input
        try:
            data = json.loads(input_data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON input: {e}")
            raise
        
        message = data.get("message", "")
        history = data.get("history", [])
        
        if not message:
            logger.error("No message provided in input data")
            raise ValueError("No message provided")
        
        logger.info(f"Processing request with message length: {len(message)}")
        
        # Get AI response
        response = get_ai_response(message, history)
        
        # Return JSON response
        output = {
            "response": response,
            "status": "success"
        }
        
        logger.info("Response generated successfully, sending to stdout")
        print(json.dumps(output))
        
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
        error_output = {
            "response": f"Error: {str(e)}",
            "status": "error"
        }
        print(json.dumps(error_output))
        sys.exit(1)

if __name__ == "__main__":
    main()

