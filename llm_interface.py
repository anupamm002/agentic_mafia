from openai import OpenAI
from typing import Dict, Any, Optional, TypeVar, Type
import json
import os
import re
from dataclasses import fields

T = TypeVar('T')

class LLMInterface:
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gpt-5-nano", base_url: Optional[str] = None):
        self.api_key = api_key or os.getenv("YOUR_API_KEY")
        if not self.api_key:
            raise ValueError("YOUR_API_KEY not provided. Set YOUR_API_KEY environment variable or pass api_key parameter.")
        
        self.base_url = base_url or os.getenv("BASE_URL")
        if not self.base_url:
            raise ValueError("BASE_URL not provided. Set BASE_URL environment variable or pass base_url parameter.")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        self.model_name = model_name
    
    def generate_response(self, prompt: str, temperature: float = 0.7) -> str:
        try:
            # gpt-5-nano only supports temperature=1
            actual_temperature = 1.0 if self.model_name.startswith("gpt-5") else temperature
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{'role': 'user', 'content': prompt}],
                max_tokens=1000,
                temperature=actual_temperature
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error generating response: {e}")
            return "ERROR: Could not generate response"
    
    def generate_json_response(self, prompt: str, temperature: float = 0.7) -> Dict[Any, Any]:
        response_text = self.generate_response(prompt, temperature)
        try:
            # Try to extract JSON from response
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                json_text = response_text
            
            return json.loads(json_text)
        except json.JSONDecodeError:
            print(f"Failed to parse JSON response: {response_text}")
            return {"error": "Invalid JSON response", "raw_response": response_text}
    
    def generate_structured_response(self, prompt: str, response_class: Type[T], temperature: float = 0.7) -> T:
        """Generate a structured response using the specified dataclass"""
        field_names = [f.name for f in fields(response_class)]
        field_descriptions = []
        
        for field in fields(response_class):
            field_type = field.type
            if hasattr(field_type, '__origin__') and field_type.__origin__ is Optional:
                field_type = field_type.__args__[0]
            
            type_hint = ""
            if field_type == str:
                type_hint = " (string)"
            elif field_type == bool:
                type_hint = " (true/false)"
            elif field_type == int:
                type_hint = " (number)"
                
            field_descriptions.append(f"- {field.name}{type_hint}")
        
        structured_prompt = f"""{prompt}

IMPORTANT: Respond ONLY with the following format (no extra text, no markdown, no explanations):
{chr(10).join(field_descriptions)}

Example format:
{chr(10).join(f"- {field.name}: [your response here]" for field in fields(response_class))}"""
        
        response_text = self.generate_response(structured_prompt, temperature)
        
        # Parse structured response
        result_dict = {}
        for field in fields(response_class):
            # Look for the field in the response
            pattern = rf"- {field.name}:\s*(.+?)(?=\n-|\n$|$)"
            match = re.search(pattern, response_text, re.MULTILINE | re.DOTALL)
            
            if match:
                value = match.group(1).strip()
                
                # Convert to appropriate type
                if field.type == bool:
                    result_dict[field.name] = value.lower() in ['true', 'yes', '1']
                elif field.type == int:
                    try:
                        result_dict[field.name] = int(value)
                    except ValueError:
                        result_dict[field.name] = 0
                else:
                    result_dict[field.name] = value
            else:
                # Default values for missing fields
                if field.type == bool:
                    result_dict[field.name] = False
                elif field.type == int:
                    result_dict[field.name] = 0
                elif field.type == str:
                    result_dict[field.name] = ""
        
        try:
            return response_class(**result_dict)
        except Exception as e:
            print(f"Error creating structured response: {e}")
            print(f"Raw response: {response_text}")
            # Return default instance
            default_dict = {}
            for field in fields(response_class):
                if field.type == bool:
                    default_dict[field.name] = False
                elif field.type == int:
                    default_dict[field.name] = 0
                elif field.type == str:
                    default_dict[field.name] = ""
            return response_class(**default_dict)