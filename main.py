import json
import os
import argparse
import traceback
from datetime import datetime
from src.evaluation import run_evaluation
from src.prompt_optimization.prompt_rewrite import PromptRewriter
from src.prompt_optimization.error_analysis_with_reasoning import PromptOptimizer
    
def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Run LLM evaluation on test cases')
    
    parser.add_argument('--model', '-m', 
                        default="us.amazon.nova-pro-v1:0",
                        help='Model ID to use for evaluation')
    
    parser.add_argument('--test-file', '-t', 
                        default="./src/data/test_cases.json",
                        help='Path to test cases JSON file')
    
    parser.add_argument('--results-dir', '-r', 
                        default="./src/results",
                        help='Directory to save results')
    
    parser.add_argument('--verbose', '-v', 
                        action='store_true',
                        help='Enable verbose output')
    
    parser.add_argument("--max-iterations", type=int, default=5, help="Maximum optimization iterations")

    return parser.parse_args()


def main():
    """Main function to run the evaluation."""
    # Parse command line arguments
    args = parse_arguments()
    
    # Print configuration
    print(f"Configuration:")
    print(f"  Model ID: {args.model}")
    print(f"  Test file: {args.test_file}")
    print(f"  Results directory: {args.results_dir}")
    print(f"  Verbose mode: {'Enabled' if args.verbose else 'Disabled'}")
    print(f"  Max iterations: {args.max_iterations}")

    # Initialize optimizer and rewriter
    optimizer = PromptOptimizer()
    rewriter = PromptRewriter()
    
    # Ensure results directory exists
    os.makedirs(args.results_dir, exist_ok=True)

    # Create a list to store iteration data
    iterations_data = []

    # Ensure test file exists
    if not os.path.exists(args.test_file):
        print(f"Error: Test file '{args.test_file}' not found")
        return 1
    
    # Load initial test cases
    try:
        with open(args.test_file, 'r') as file:
            test_data = json.load(file)
        print(f"Loaded {len(test_data.get('test_cases', []))} test cases")
        
        # Get the initial prompt template
        current_prompt_template = test_data.get('prompt_template')
        
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in test file '{args.test_file}'")
        return 1
    except Exception as e:
        print(f"Error loading test file: {str(e)}")
        return 1

    # Run optimization iterations
    for i in range(0, args.max_iterations):
        print(f"\n\n======== ITERATION {i+1}/{args.max_iterations} ========")
        
        # Ensure current prompt template is in test data
        test_data['prompt_template'] = current_prompt_template
        
        # Run evaluation
        print("\nStarting evaluation...")
        start_time = datetime.now()
        
        try:
            
            # Run evaluation with current prompt template
            results = run_evaluation(test_data, args.model, args.results_dir)
            
            # Print summary
            elapsed_time = datetime.now() - start_time
            print("\nEvaluation complete!")
            print(f"Time taken: {elapsed_time}")
            print(f"Total test cases: {results['stats']['total']}")
            print(f"Failed calls: {results['stats']['llm_fail']}")
            
            # Print success rate if available
            if 'task_succeed' in results['stats']:
                success_rate = results['stats']['task_succeed'] / results['stats']['total'] * 100
                print(f"Task success rate: {success_rate:.2f}%")
            

            # Get feedback on the current results
            print("\nGenerating feedback for prompt improvement...")
            feedback = optimizer.get_prompt_feedback(results, iteration=i)
            print(f"Feedback generated.")

            # Generate improved prompt
            print("Generating improved prompt...")
            improved_result = rewriter.improving_prompt_with_feedback(
                current_template=current_prompt_template,
                critique_feedbacks=feedback
            )

            # Get the improved template
            improved_template = improved_result.get('improved_template', current_prompt_template)
            print(f"Improved prompt created.")

            # Create iteration data dictionary
            iteration_data = {
                "iteration": i,
                "current_prompt_template": current_prompt_template,
                "success_rate": success_rate,
                "feedback": feedback,
                "improved_result": improved_result
            }
            
            # Add to the list of all iterations
            iterations_data.append(iteration_data)
            
            print("\n===== IMPROVED TEMPLATE =====")
            print(improved_template)
            print("============================\n")
            # Update current prompt template for next iteration
            current_prompt_template = improved_template
                
        except Exception as e:
            print(f"Error during iteration {i+1}: {str(e)}")
            if args.verbose:
                traceback.print_exc()
            # Continue to next iteration
            continue


    # Save the cumulative iteration data
    iteration_file_path = os.path.join(args.results_dir, f"optimization_iteratiion_log.json")
    with open(iteration_file_path, 'w') as f:
        json.dump(iterations_data, f, indent=2)
    print(f"Saved iteration data to {iteration_file_path}")
    
    print("\nOptimization process complete!")
    return 0

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)