import json
import boto3
import traceback
import os
from datetime import datetime
from tqdm import tqdm
from string import Template
import concurrent.futures

from src.utils.parsers import load_json_from_llm_result
from src.utils.evaluation import evaluate_test_results 

def process_single_test_case(test_case, prompt_template, target_model_id, case_idx, temperature=0.1, top_p=0.9, max_tokens=2000):
    """
    Process a single test case and return the result
    
    Args:
        test_case (dict): The test case to process
        prompt_template (str): Template string with {user_question} placeholder
        target_model_id (str): Model ID to use for inference
        case_idx (int): Case index for tracking
        temperature (float): Temperature setting for inference
        top_p (float): Top-p setting for inference
        max_tokens (int): Maximum tokens to generate
        
    Returns:
        dict: The processed test case result
    """
    user_question = test_case.get("user_question", "")
    groundtruth_result = test_case.get("ground_truth", "")
    generated_text = ""

    try:
        # Format the prompt template with the user question        
        template = Template(prompt_template)
        formatted_prompt = template.safe_substitute(user_question=user_question)

        # Call the Bedrock Converse API
        generated_text = call_bedrock_converse(
            prompt=formatted_prompt,
            model_id=target_model_id,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens
        )
        #print("############################")
        #print("Prompt: ")
        #print(formatted_prompt)
        #print("Prediction: ")
        #print(generated_text)
        #print("############################")

        results_llm = load_json_from_llm_result(generated_text)
        
        # Create result entry
        case_result = {
            "user_question": user_question,
            "ground_truth": groundtruth_result,
            "prediction": results_llm["prediction"],
            "explanation": results_llm["explanation"],
            "case_type": "llm_success" 
        }
        
    except Exception as e:
        # Handle errors
        error_trace = traceback.format_exc()
        case_result = {
            "user_question": user_question,
            "ground_truth": groundtruth_result,
            "prediction": "Error",
            "explanation": "Original generated text: " +  generated_text,
            "case_type": "llm_error"
        }
        
        print(f"\nError in test case {case_idx+1}:")
        print(error_trace)
    
    # Add metadata for visualization
    case_result.update({
        "case_idx": case_idx + 1
    })
    
    return case_result


def execute_test_cases(data, target_model_id, output_file=None, max_workers=8):
    """
    Execute all test cases in parallel and track results
    
    Args:
        data (dict): Data containing prompt template and test cases
        target_model_id (str): Model ID to use for inference
        output_file (str, optional): Path to save results. If None, results aren't saved.
        max_workers (int): Maximum number of parallel workers to use
        
    Returns:
        dict: Results of all test cases with statistics
    """
    # Initialize counters and data structures
    prompt_template = data.get("prompt_template", "")
    test_cases = data.get("test_cases", [])
    total_cases = len(test_cases)
    
    suite_results = {
        "prompt_template": prompt_template,
        "test_cases": [],
        "stats": {"total": total_cases, "llm_successful": 0, "llm_fail": 0, "task_succeed": 0},
    }

    # Create a list to store completed results that might come back in any order
    completed_results = [None] * total_cases
    
    # Process test cases in parallel
    with tqdm(total=total_cases, desc="Processing Test Cases") as pbar:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks to the executor
            future_to_idx = {
                executor.submit(
                    process_single_test_case,
                    test_case,
                    prompt_template,
                    target_model_id,
                    case_idx,
                ): case_idx
                for case_idx, test_case in enumerate(test_cases)
            }
            
            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_idx):
                case_idx = future_to_idx[future]
                try:
                    case_result = future.result()
                    completed_results[case_idx] = case_result
                    
                    # Update statistics
                    if case_result["case_type"] == "llm_success":
                        suite_results["stats"]["llm_successful"] += 1
                    else:
                        suite_results["stats"]["llm_fail"] += 1
                    
                except Exception as exc:
                    print(f"\nError processing case {case_idx+1}: {exc}")
                    # Create an error result if the entire future fails
                    completed_results[case_idx] = {
                        "user_question": test_cases[case_idx].get("user_question", ""),
                        "ground_truth": test_cases[case_idx].get("ground_truth", ""),
                        "prediction": "Executor Error",
                        "explanation": f"Error in executor: {str(exc)}",
                        "case_type": "llm_error",
                        "case_idx": case_idx + 1
                    }
                    suite_results["stats"]["llm_fail"] += 1
                
                # Update progress bar
                pbar.update(1)
                pbar.set_postfix({
                    "Success": f"{suite_results['stats']['llm_successful']}/{total_cases}",
                })
    
    # Add all results in correct order
    suite_results["test_cases"] = completed_results
    
    # Evaluate task success (comparing predictions with ground truth)
    suite_results = evaluate_test_results(suite_results)
    
    # Save results if output file is specified
    if output_file:
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        with open(output_file, "w") as f:
            json.dump(suite_results, f, indent=2)
        print(f"Results saved to {output_file}")

    return suite_results

def run_evaluation(test_data, model_id, results_dir="results"):
    """
    Run evaluation and save results with timestamp
    
    Args:
        test_data (dict): Test data with prompt template and test cases
        model_id (str): Model ID to run inference with
        results_dir (str): Directory to save results
        
    Returns:
        dict: Evaluation results
    """
    # Create results directory if it doesn't exist
    os.makedirs(results_dir, exist_ok=True)
    
    # Create output filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(results_dir, f"test_results_{timestamp}.json")
    
    # Execute test cases and get results
    results = execute_test_cases(test_data, model_id, output_file)
    
    return results



def call_bedrock_converse(prompt, model_id, temperature=0.7, top_p=250, max_tokens=4096):
    """
    Call Amazon Bedrock using the Converse API to generate a response.
    
    Args:
        prompt (str): The prompt to send to the model
        model_id (str): The model ID (e.g., "anthropic.claude-3-sonnet-20240229-v1:0")
        temperature (float): Controls randomness (0-1)
        top_k (int): Limits token selection to top K options
        max_tokens (int): Maximum tokens to generate
        
    Returns:
        dict: The model's response
    """
    # Initialize Bedrock client
    bedrock_runtime = boto3.client(
        service_name="bedrock-runtime",
    )
    
    # Make the API call
    response = bedrock_runtime.converse(
        modelId=model_id,
        messages= [
            {
                "role": "user",
                "content": [
                    {"text": prompt}
                ]
            }
        ],
        inferenceConfig= {
            "temperature": temperature,
            "maxTokens": max_tokens
        }
    )
    
    output_message = response['output']['message']

    return "\n".join(x["text"] for x in output_message["content"])