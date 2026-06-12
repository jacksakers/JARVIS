"""
A generic CLI harness to test any JARVIS skill in isolation, 
exactly as the LLM would interact with it.
"""
import json
import sys
from pathlib import Path

# Add parent directory to path so we can import app as a package
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the skills you want to test here
from app.skills.web_skills import WebSearchSkill, ReadWebpageSkill

def run_interactive_tester(skill_instance):
    print(f"\n" + "="*50)
    print(f"🧪 TESTING SKILL: {skill_instance.name}")
    print(f"📝 Description: {skill_instance.description}")
    print("="*50)
    
    # Show what the LLM sees
    print("\n[Schema presented to LLM]:")
    # print(json.dumps(skill_instance.get_ollama_tool_schema(), indent=2))
    print("-" * 50)

    while True:
        print("\nEnter arguments as a JSON dictionary (or type 'quit' to exit).")
        print("Example: {\"query\": \"SpaceX latest news\", \"max_results\": 2}")
        
        user_input = input("\nJSON Args > ")
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            break
            
        try:
            # 1. Parse user input into a Python dictionary
            args_dict = json.loads(user_input)
            
            # 2. Pass dictionary into the Pydantic model for validation
            # This exactly mimics how the FastAPI backend routes Ollama's output
            validated_params = skill_instance.input_model(**args_dict)
            
            # 3. Execute the skill
            print("\n⚙️  Executing...")
            result = skill_instance.execute(validated_params)
            
            print("\n✅ RESULT:")
            print(result)
            
        except json.JSONDecodeError:
            print("\n❌ Error: Invalid JSON format. Make sure you use double quotes for keys and strings.")
        except Exception as e:
            print(f"\n❌ Validation or Execution Error: {e}")

if __name__ == "__main__":
    # You can swap this out for any skill you want to test!
    # Example: skill_to_test = SaveMemorySkill()
    skill_to_test = ReadWebpageSkill()
    
    run_interactive_tester(skill_to_test)