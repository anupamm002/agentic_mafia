#!/usr/bin/env python3
"""
Mafia Multi-Agent Game - Phase 1
A complete implementation of the Mafia party game using AI agents
"""

import os
import sys
from llm_interface import LLMInterface
from game_orchestrator import GameOrchestrator

def main():
    """Main entry point for the Mafia game"""
    
    # Check for API key
    api_key = os.getenv("YOUR_API_KEY")
    base_url = os.getenv("BASE_URL")
    
    if not api_key:
        print("❌ Error: YOUR_API_KEY environment variable not set")
        print("Please set your API key:")
        print("export YOUR_API_KEY=your_api_key_here")
        sys.exit(1)
    
    if not base_url:
        print("❌ Error: BASE_URL environment variable not set")
        print("Please set your base URL:")
        print("export BASE_URL=your_base_url_here")
        sys.exit(1)
    
    try:
        # Initialize LLM interface
        startup_msg = "🚀 Starting Mafia Multi-Agent Game (Phase 1)"
        print(startup_msg)
        
        model_name = "gemini-2.0-flash-001"
        # model_name = "gpt-5-nano"
        
        model_msg = f"🤖 Using {model_name} for AI agents"
        print(model_msg)

        llm = LLMInterface(api_key=api_key, model_name=model_name, base_url=base_url)
        
        # Game configuration
        num_mafia = 2  # Change this to adjust Mafia count
        log_intermediate_contexts = False  # Set to False to disable context logging during game
        
        # Create game orchestrator first to get access to logging
        game = GameOrchestrator(
            llm_interface=llm,
            max_discussion_rounds=2,
            max_mafia_iterations=3,
            num_mafia=num_mafia,
            observer_only=True,  # Only show observer info
            log_intermediate_contexts=log_intermediate_contexts
        )
        
        # Log the startup messages
        game._observer_info(startup_msg.replace("🚀 ", ""))
        game._observer_info(model_msg.replace("🤖 ", ""))
        
        # Initialize and play game
        game.initialize_game()
        winner = game.play_game()
        
        completion_msg = f"\n✅ Game completed! Winner: {winner.upper()}"
        print(completion_msg)
        game._observer_info(completion_msg.replace("\n", ""))
        
    except KeyboardInterrupt:
        print("\n\n⏹️ Game interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error during game: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()