#!/usr/bin/env python3
"""
Simple test file to trigger bot review.
This file demonstrates basic Python functionality.
"""


def calculate_sum(a: int, b: int) -> int:
    """Calculate the sum of two integers."""
    return a + b


def greet_user(name: str) -> str:
    """Generate a greeting message."""
    return f"Hello, {name}! Welcome to the AI review bot test."


if __name__ == "__main__":
    result = calculate_sum(5, 3)
    message = greet_user("Developer")
    print(f"Sum: {result}")
    print(message)
