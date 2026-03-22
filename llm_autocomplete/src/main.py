import sys
import os
from .engine import AutocompleteEngine
from .types import EngineConfig

def main():
    if len(sys.argv) < 2:
        print("Usage: python -m src.main 'Your Project Idea'")
        sys.exit(1)

    goal = sys.argv[1]
    mode = "coder"
    if len(sys.argv) > 2 and sys.argv[2] == "--mode":
         mode = sys.argv[3]
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Please set OPENAI_API_KEY environment variable.")
        sys.exit(1)

    print(f"Initializing Autocomplete Engine for: {goal} (Mode: {mode})")
    
    config = EngineConfig(api_key=api_key)
    engine = AutocompleteEngine(goal=goal, config=config, mode=mode)
    
    try:
        engine.run()
    except Exception as e:
        print(f"Engine failed: {e}")

if __name__ == "__main__":
    main()
