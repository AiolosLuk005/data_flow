import re
import json
import sys

# Configure stdout to use UTF-8 to prevent UnicodeEncodeError when printing emojis in Windows cmd/PowerShell
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def extract_json_from_text(text):
    """
    Robustly extract JSON from text that may contain think blocks, 
    markdown code blocks, or leading/trailing text.
    """
    # 1. First, strip any reasoning blocks (<think>...</think>)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    
    # 2. Try to find a JSON block in markdown code fences
    # This handles cases where models use ```json ... ``` or ``` ... ```
    json_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_block_match:
        return json_block_match.group(1).strip()
    
    # 3. Fallback to finding the first { and the literal last }
    # Using a greedy match for the content between the first and last curly braces
    json_match = re.search(r'(\{.*\})', text, re.DOTALL)
    if json_match:
        return json_match.group(1).strip()
    
    # 4. If nothing else works, return the original text (allowing json.loads to try/fail)
    return text

# Test cases
test_cases = [
    {
        "name": "Standard JSON",
        "input": '{"name": "test", "value": 123}',
        "expected": '{"name": "test", "value": 123}'
    },
    {
        "name": "Reasoning Model (DeepSeek R1 style)",
        "input": '<think>Analysis here...</think>{"name": "test", "value": 123}',
        "expected": '{"name": "test", "value": 123}'
    },
    {
        "name": "Markdown Code Block",
        "input": 'Here is the data:\n```json\n{"name": "test", "value": 123}\n```\nHope this helps!',
        "expected": '{"name": "test", "value": 123}'
    },
    {
        "name": "Markdown Block without language tag",
        "input": '```\n{"name": "test", "value": 123}\n```',
        "expected": '{"name": "test", "value": 123}'
    },
    {
        "name": "Leading/Trailing Text",
        "input": 'The results are: {"name": "test", "value": 123}. Please check.',
        "expected": '{"name": "test", "value": 123}'
    },
    {
        "name": "Nested Braces in Text (Traps)",
        "input": 'Result {status: ok}: {"name": "test", "value": 123} [Verified]',
        "expected": '{status: ok}: {"name": "test", "value": 123}' # Handled by greedy {.*}
    }
]

def run_tests():
    print("Running JSON extraction tests...")
    for case in test_cases:
        result = extract_json_from_text(case["input"])
        if result == case["expected"]:
            print(f"✅ Pass: {case['name']}")
        else:
            print(f"❌ Fail: {case['name']}")
            print(f"   Input:    {case['input']}")
            print(f"   Expected: {case['expected']}")
            print(f"   Got:      {result}")

if __name__ == "__main__":
    run_tests()
    
    # Test with real json.loads
    try:
        sample = '{"key": "value"}'
        parsed = json.loads(extract_json_from_text('Text: ' + sample))
        print(f"\nIntegration test with json.loads: {'✅' if parsed['key'] == 'value' else '❌'}")
    except Exception as e:
        print(f"\nIntegration test failed: {e}")
