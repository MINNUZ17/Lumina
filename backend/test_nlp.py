import sys
import os

# Add the current directory to sys.path to import app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import classify_feedback

test_cases = [
    "This route is amazing, very safe and bright!",
    "The road was pitch black and very scary. I felt unsafe.",
    "It's okay, but some parts are a bit dark.",
    "Great navigation, thank you!",
    "Too many turns, and the lighting is bad.",
    "Excellent lighting and very bustling area."
]

for tc in test_cases:
    category = classify_feedback(tc)
    print(f"Feedback: '{tc}'\nCategory: {category}\n")
