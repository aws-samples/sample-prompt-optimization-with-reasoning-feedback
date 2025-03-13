"""
Evaluation module for testing LLM responses against expected outputs.
"""
from src.evaluation.executor import process_single_test_case, execute_test_cases, run_evaluation

__all__ = [
    'process_single_test_case', 
    'execute_test_cases', 
    'run_evaluation',
]