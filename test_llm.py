#!/usr/bin/env python3
"""
Test script for LLM interface
"""

import os
import time
from llm_interface import LLMInterface
from structured_responses import DiscussionResponse

def test_llm():
    # Check for API key
    api_key = os.getenv("YOUR_API_KEY")
    base_url = os.getenv("BASE_URL")
    
    if not api_key:
        print("❌ Error: YOUR_API_KEY environment variable not set")
        print("Please set your API key:")
        print("export YOUR_API_KEY=your_api_key_here")
        return
    
    if not base_url:
        print("❌ Error: BASE_URL environment variable not set")
        print("Please set your base URL:")
        print("export BASE_URL=your_base_url_here")
        return

    try:
        print("🧪 Testing LLM Interface...")
        
        model_name = "gemini-2.0-flash-001"

        # Initialize LLM
        llm = LLMInterface(api_key=api_key, model_name=model_name, base_url=base_url)
        print(f"📋 Using model: {model_name}")
        
        # Test basic response
        print("\n1. Testing basic response...")
        start_time = time.time()
        response = llm.generate_response("Say hello in a friendly way", temperature=0.5)
        end_time = time.time()
        duration = end_time - start_time
        print(f"⏱️  Time taken: {duration:.2f} seconds")
        print(f"Response: {response}")
        
        # Test structured response
        print("\n2. Testing structured response...")
        prompt = """You are in a Mafia game discussion. Someone just accused you of being suspicious.
        
Do you want to speak? If yes, what will you say?
Keep response under 50 words.
Urgency (1-5): How urgent is it for you to respond?"""
        
        start_time = time.time()
        structured_response = llm.generate_structured_response(prompt, DiscussionResponse)
        end_time = time.time()
        duration = end_time - start_time
        print(f"⏱️  Time taken: {duration:.2f} seconds")
        print(f"Speak: {structured_response.speak}")
        print(f"Comment: {structured_response.comment}")
        print(f"Urgency: {structured_response.urgency}")
        
        print("\n✅ LLM interface test completed successfully!")
        
    except Exception as e:
        print(f"❌ Error testing LLM: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_llm()