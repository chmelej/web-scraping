import os
import json
from config.settings import ANTHROPIC_API_KEY, OPENAI_API_KEY

# Minimal mock client logic if keys are missing,
# or real logic if libraries installed and keys present.

def call_llm(model, prompt, system=None, max_tokens=200, temperature=0.0):
    """
    Generic LLM caller.
    Supports:
    - OpenAI (gpt-*)
    - Anthropic (claude-*)
    - Ollama (local) - fallback
    """

    # 1. Anthropic
    if model.startswith('claude'):
        if ANTHROPIC_API_KEY:
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
                message = client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system or "",
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                return message.content[0].text
            except ImportError:
                print("Anthropic library not installed")
        else:
            print("Anthropic API Key missing")

    # 2. OpenAI
    elif model.startswith('gpt'):
        if OPENAI_API_KEY:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=OPENAI_API_KEY)
                messages = []
                if system:
                    messages.append({"role": "system", "content": system})
                messages.append({"role": "user", "content": prompt})

                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                return response.choices[0].message.content
            except ImportError:
                print("OpenAI library not installed")
        else:
            print("OpenAI API Key missing")

    # 3. Ollama / Fallback logic
    # Try local ollama
    try:
        import requests
        # Assume Ollama default port
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        resp = requests.post("http://localhost:11434/api/generate", json=payload, timeout=30)
        if resp.status_code == 200:
            return resp.json()['response']
    except:
        pass

    # Mock response for testing/dry-run if nothing works
    print(f"LLM Call Simulated: {model}")
    # Return valid JSON for testing opening hours
    if "opening" in prompt.lower() or "otevírací" in prompt.lower():
        return '{"days": [{"day": "monday", "open": "09:00", "close": "17:00"}]}'

    return "{}"
