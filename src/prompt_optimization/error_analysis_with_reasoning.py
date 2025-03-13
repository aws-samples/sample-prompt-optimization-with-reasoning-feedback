import json
from string import Template
import boto3
from botocore.config import Config

class PromptOptimizer:
    """Class for optimizing prompts based on error analysis"""
    
    def __init__(self, model_id=""):
        # "us.deepseek.r1-v1:0" deepseek reasoning 
        # us.anthropic.claude-3-7-sonnet-20250219-v1:0 sonnet 3.7 reasoning
        #self.model_id = "us.deepseek.r1-v1:0"
        self.model_id = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
        self.suggestion_history = ""  # Initialize empty suggestion history
        self.critique_prompt_template = """
        Analyze the classification performance and provide detailed reasoning for prompt improvements:

        Current Template:
        <current_template>
        ${input_current_template}
        </current_template>

        Evaluation Results:
        <evaluation_results>
        ${evaluation_results}
        </evaluation_results>

        IMPORTANT: If you need to identify errors between predictions and ground truth, focus on understanding the explanation part and critique any incorrect explanations with respect to the ground truth.

        Follow these thinking steps in order:

        1. STEP 1 - Error Pattern Analysis:
           - List ALL misclassified cases
           - Group similar errors
           - Focus on how the prompt's instructions led to these errors

        2. STEP 2 - Prompt-Specific Root Cause Investigation:
           For each error pattern identified above, analyze:
           - Which parts of the current prompt led to misinterpretation?
           - Are there ambiguous or missing instructions?
           - Are the classification criteria clearly defined?
           - Is the format/structure of the prompt causing confusion?

        3. STEP 3 - Historical Context:
           Previous Iterative Suggestions: 
           <suggestion_history>
           ${suggestion_history}        
           </suggestion_history>

           Analyze only prompt-related changes:
           - Which prompt modifications were effective/ineffective?
           - Which instruction clarity issues persist?
           - What prompt elements still need refinement?
           - Focus more on recent iterations 

        4. STEP 4 - Prompt Improvement Ideas:
           Suggest only changes to prompt instructions and structure:
           - Clearer classification criteria
           - Better examples or explanations
           - More precise instructions
           - Better prompt structure or organization
           - Specific wording improvements
          
           AVOID suggesting:
           Adding more training data
           Modifying the model
           Changes to the underlying AI system
           Adding new model capabilities
           Adding directly the evalution samples into the suggesting

           
           Base on the Current Template between <current_template> </current_template>
           
           Output your final improvement suggestions between <suggestion> </suggestion> 

        """
        
        # Initialize Bedrock client
        config = Config(
            connect_timeout=300,
            read_timeout=300
        )
        self.bedrock_runtime = boto3.client(service_name='bedrock-runtime', config=config)
    
    def reset_suggestion_history(self):
        """Reset the suggestion history to empty"""
        self.suggestion_history = ""
        
    def error_analysis_with_reasoning(self, prompt, temperature=1, max_tokens=8192, 
                                     thinking_budget=4096, system_prompt=""):
        """
        Call Amazon Bedrock using the Converse API with thinking capability
        
        Args:
            prompt (str): The prompt to send to the model
            temperature (float): Controls randomness (0-1)
            max_tokens (int): Maximum tokens to generate
            thinking_budget (int): Maximum tokens to think
            system_prompt (str): System prompt to guide the model
            
        Returns:
            dict: The model's response with thinking and other content
        """
        # Format system prompt as required by Converse API
        formatted_system_prompt = [{"text": system_prompt}] if system_prompt else []
        
        # Format the message for Converse API
        messages = [
            {
                "role": "user",
                "content": [{"text": prompt}]
            }
        ]

        # Configure inference parameters
        inference_config = {
            "temperature": temperature,
            "maxTokens": max_tokens
        }
        
        if "sonnet" in self.model_id:
            # Configure reasoning parameters
            reasoning_config = {
                "thinking": {
                    "type": "enabled",
                    "budget_tokens": thinking_budget
                },
            }

            # Make the API call
            response = self.bedrock_runtime.converse(
                modelId=self.model_id,
                messages=messages,
                system=formatted_system_prompt,
                inferenceConfig=inference_config,
                additionalModelRequestFields=reasoning_config
            )
        elif "deepseek" in self.model_id: 
            # Make the API call
            response = self.bedrock_runtime.converse(
                modelId=self.model_id,
                messages=messages,
                inferenceConfig=inference_config,
                system=formatted_system_prompt,
            )
        
        # Initialize result dictionary
        result = {}
        
        # Extract content blocks using the exact pattern provided
        content_blocks = response["output"]["message"]["content"]
        
        reasoning = None
        text = None
        
        # Process each content block to find reasoning and response text
        for block in content_blocks:
            if "reasoningContent" in block:
                reasoning = block["reasoningContent"]["reasoningText"]["text"]
            if "text" in block:
                text = block["text"]
        
        # Add the extracted contents to the result dictionary
        if reasoning:
            result['reasoning'] = reasoning
            #print("\n===== REASONING =====")
            #print(reasoning)
            #print("=====================\n")
        
        if text:
            result['text'] = text
            #print("\n===== RESPONSE =====")
            #print(text)
            #print("====================\n")
        
        # Add token usage information to result
        if 'usage' in response:
            result['token_usage'] = response['usage']
        
        return result
    
    def generate_critique_prompt(self, baseline_result):
        """Generate a critique prompt based on baseline results and the current suggestion history"""
        template = Template(self.critique_prompt_template)
        current_critique_prompt = template.safe_substitute(
            input_current_template=baseline_result['prompt_template'],
            evaluation_results=json.dumps(baseline_result['test_cases']),
            suggestion_history=self.suggestion_history
        )
        return current_critique_prompt
    
    def get_prompt_feedback(self, baseline_result, max_tokens=4096, thinking_budget=2048, iteration=1):
        """
        Get feedback on a prompt using error analysis
        
        Args:
            baseline_result (dict): The baseline evaluation results
            max_tokens (int): Maximum tokens to generate
            thinking_budget (int): Maximum tokens to think
            iteration (int): Current iteration number
            
        Returns:
            dict: Feedback with reasoning and suggestions
        """
        critique_prompt = self.generate_critique_prompt(baseline_result)
        
        print(f"Current suggestion history length: {len(self.suggestion_history)} characters")
        
        feedbacks = self.error_analysis_with_reasoning(
            critique_prompt, 
            max_tokens=max_tokens,
            thinking_budget=thinking_budget
        )
        
        # Update suggestion history with the new feedback
        if 'text' in feedbacks:
            # Add a timestamp or iteration marker to the history
            history_entry = f"\n--- Iteration {iteration} Feedback ---\n{feedbacks['text']}\n"
            self.suggestion_history += history_entry
            print(f"Updated suggestion history (now {len(self.suggestion_history)} characters)")
        
        return feedbacks['text']


# Example usage
if __name__ == "__main__":
    # Initialize the optimizer
    optimizer = PromptOptimizer()
    
    # Example baseline result with the format you provided
    baseline_result = {
        'prompt_template': "Classify the following customer service inquiry into one of these categories...",
        'test_cases': [
            {
                "user_question": "I need my secret code changed for the plastic rectangle I use at the money machine, and while you're at it, I want to make sure my mobile number is up to date so I get those little messages when I use it.", 
                "ground_truth": "PIN_RESET", 
                "prediction": ["CONTACT_INFO_UPDATE"], 
                "explanation": "I want to make sure my mobile number is up to date so I get those little messages when I use it. is a request to update contact information, which is classified under 'CONTACT_INFO_UPDATE'.", 
                "case_type": "llm_success", 
                "case_idx": 1, 
                "task_succeed": False
            },
        ]
    }
    
    # Run multiple iterations to demonstrate history accumulation
    for i in range(1, 3):  # Run 2 iterations
        # Get feedback on the prompt
        feedback = optimizer.get_prompt_feedback(baseline_result, iteration=i)
        
        # In a real application, you would implement the suggestions here
        # and update the baseline_result with a new prompt and evaluation
    
    print("Final suggestion history:")
    print(optimizer.suggestion_history)
    


