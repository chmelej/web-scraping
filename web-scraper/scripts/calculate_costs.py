#!/usr/bin/env python3
import locale

# Set locale for currency formatting (optional, defaults to C if not found)
try:
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
except locale.Error:
    pass

def calculate_costs():
    # Pricing per 1,000,000 tokens (USD)
    # Based on search results for Jan 2026 (Fictional/Preview context)
    # Cache Read is estimated at 10% of Input price where not explicitly found, 
    # consistent with 2.5 Flash/Lite ratios.
    PRICING = {
        "gemini-2.5-flash-lite": {
            "input": 0.10,
            "output": 0.40,
            "cache": 0.01
        },
        "gemini-3-pro-preview": {
            "input": 2.00,
            "output": 12.00,
            "cache": 0.20  # Estimated 10% of input
        },
        "gemini-2.5-flash": {
            "input": 0.30,
            "output": 2.50,
            "cache": 0.03
        },
        "gemini-3-flash-preview": {
            "input": 0.50,
            "output": 3.00,
            "cache": 0.05
        }
    }

    # Usage Statistics
    usage_data = [
        {
            "model": "gemini-2.5-flash-lite",
            "reqs": 14,
            "input_tokens": 114_448,
            "cache_reads": 0,
            "output_tokens": 1_638
        },
        {
            "model": "gemini-3-pro-preview",
            "reqs": 36,
            "input_tokens": 355_052,
            "cache_reads": 1_169_610,
            "output_tokens": 18_833
        },
        {
            "model": "gemini-2.5-flash",
            "reqs": 1,
            "input_tokens": 0,
            "cache_reads": 0,
            "output_tokens": 0
        },
        {
            "model": "gemini-3-flash-preview",
            "reqs": 2,
            "input_tokens": 95_444,
            "cache_reads": 94_449,
            "output_tokens": 1_053
        }
    ]

    print(f"{'Model':<25} | {'Input Cost':<12} | {'Cache Cost':<12} | {'Output Cost':<12} | {'Total Cost':<12}")
    print("-" * 85)

    grand_total = 0.0

    for item in usage_data:
        model = item["model"]
        prices = PRICING.get(model)
        
        if not prices:
            print(f"Warning: No pricing found for {model}")
            continue

        # Calculate costs (Prices are per 1M tokens)
        input_cost = (item["input_tokens"] / 1_000_000) * prices["input"]
        cache_cost = (item["cache_reads"] / 1_000_000) * prices["cache"]
        output_cost = (item["output_tokens"] / 1_000_000) * prices["output"]
        
        total_model_cost = input_cost + cache_cost + output_cost
        grand_total += total_model_cost

        print(f"{model:<25} | ${input_cost:10.6f} | ${cache_cost:10.6f} | ${output_cost:10.6f} | ${total_model_cost:10.6f}")

    print("-" * 85)
    print(f"{'TOTAL':<25} | {'':<12} | {'':<12} | {'':<12} | ${grand_total:10.6f}")

if __name__ == "__main__":
    calculate_costs()
