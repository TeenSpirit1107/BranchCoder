#!/usr/bin/env python3
"""
AI Service for VS Code Extension
This script receives messages via stdin and returns AI responses via stdout.
"""

import json
import sys
from typing import List, Dict

def get_ai_response(message: str, history: List[Dict[str, str]]) -> str:
    """
    Process the user message and generate an AI response.
    
    Args:
        message: The current user message
        history: List of previous messages in format [{"role": "user|assistant", "content": "..."}]
    
    Returns:
        The AI response string
    """
    # TODO: Replace this with your actual AI implementation
    # Example: Using a simple echo response
    # You can integrate your actual AI model here (e.g., OpenAI, local LLM, etc.)
    
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
    
    return response

def main():
    """Main entry point - reads from stdin, processes, writes to stdout"""
    try:
        # Read input from stdin
        input_data = sys.stdin.read()
        
        if not input_data:
            raise ValueError("No input data received")
        
        # Parse JSON input
        data = json.loads(input_data)
        message = data.get("message", "")
        history = data.get("history", [])
        
        if not message:
            raise ValueError("No message provided")
        
        # Get AI response
        response = get_ai_response(message, history)
        
        # Return JSON response
        output = {
            "response": response,
            "status": "success"
        }
        
        print(json.dumps(output))
        
    except Exception as e:
        error_output = {
            "response": f"Error: {str(e)}",
            "status": "error"
        }
        print(json.dumps(error_output))
        sys.exit(1)

if __name__ == "__main__":
    main()

