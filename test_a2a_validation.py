#!/usr/bin/env python3
"""Test A2A protocol with comprehensive schema validation."""

import json
import requests
from a2a_schemas import validate_agent_card, validate_task_response


def test_with_schema_validation():
    """Test A2A endpoints with full schema validation."""
    
    base_url = "https://audience-agent.fly.dev"
    
    print("Testing A2A Protocol with Schema Validation")
    print("=" * 60)
    
    # 1. Test agent card with schema validation
    print("\n1. Agent Card Schema Validation...")
    try:
        response = requests.get(f"{base_url}/agent-card")
        response.raise_for_status()
        card = response.json()
        
        is_valid, errors = validate_agent_card(card)
        
        if is_valid:
            print("✅ Agent card passes schema validation")
            print(f"   Name: {card['name']}")
            print(f"   URL: {card.get('url', 'MISSING!')}")
            print(f"   Version: {card['version']}")
        else:
            print("❌ Agent card FAILS schema validation:")
            for error in errors:
                print(f"   - {error}")
    except Exception as e:
        print(f"❌ Failed to fetch agent card: {e}")
    
    # 2. Test .well-known endpoint
    print("\n2. Well-Known Endpoint Schema Validation...")
    try:
        response = requests.get(f"{base_url}/.well-known/agent-card.json")
        response.raise_for_status()
        card = response.json()
        
        is_valid, errors = validate_agent_card(card)
        
        if is_valid:
            print("✅ .well-known/agent-card.json passes validation")
        else:
            print("❌ .well-known/agent-card.json FAILS validation:")
            for error in errors:
                print(f"   - {error}")
    except Exception as e:
        print(f"❌ Failed to fetch .well-known: {e}")
    
    # 3. Test task response schema
    print("\n3. Task Response Schema Validation...")
    try:
        task_request = {
            "query": "test query for validation"
        }
        
        response = requests.post(
            f"{base_url}/a2a/task",
            json=task_request,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        task_response = response.json()
        
        is_valid, errors = validate_task_response(task_response)
        
        if is_valid:
            print("✅ Task response passes schema validation")
            print(f"   Task ID: {task_response['id']}")
            print(f"   Status: {task_response['status']['state']}")
        else:
            print("❌ Task response FAILS schema validation:")
            for error in errors:
                print(f"   - {error}")
    except Exception as e:
        print(f"❌ Failed task execution: {e}")
    
    # 4. Test all required agent card fields
    print("\n4. Checking all required agent card fields...")
    try:
        response = requests.get(f"{base_url}/agent-card")
        card = response.json()
        
        required_fields = [
            "name", "description", "version", "url", "protocolVersion",
            "defaultInputModes", "defaultOutputModes", "capabilities",
            "skills", "provider"
        ]
        
        missing = [f for f in required_fields if f not in card]
        if missing:
            print(f"❌ Missing required fields: {', '.join(missing)}")
        else:
            print("✅ All required fields present")
            
        # Check provider fields
        if "provider" in card:
            provider_fields = ["name", "organization", "url"]
            provider_missing = [f for f in provider_fields if f not in card["provider"]]
            if provider_missing:
                print(f"❌ Provider missing fields: {', '.join(provider_missing)}")
            else:
                print("✅ Provider has all required fields")
                
        # Check skills
        if "skills" in card and card["skills"]:
            skill = card["skills"][0]
            skill_fields = ["id", "name", "description"]
            skill_missing = [f for f in skill_fields if f not in skill]
            if skill_missing:
                print(f"❌ Skill missing fields: {', '.join(skill_missing)}")
            else:
                print("✅ Skills have required fields")
                
    except Exception as e:
        print(f"❌ Error checking fields: {e}")
    
    print("\n" + "=" * 60)
    print("Schema Validation Complete")


if __name__ == "__main__":
    test_with_schema_validation()