# prompt_rewrite.py

import json
from string import Template
import boto3
from botocore.config import Config
from src.utils.parsers import load_json_from_llm_result

class PromptRewriter:
    """Class for rewriting prompts based on feedback analysis"""
    
    def __init__(self, model_id="us.amazon.nova-pro-v1:0"):
        self.model_id = model_id
        self.guidance_prompt_improvement_template = """
        You need to improve the Current Template following the Critique Analysis.  

        Current Template:
        <current_template>
        ${input_current_template}
        </current_template>


        Instructions for improved template:
        ALWAYS KEEP THE PLACEHOLDER OF user_question
        1. Take the Current Template as a base. 
        2. Incorporate specific improvements identified in the analysis
        3. Ensure the new template maintains the basic structure but addresses the identified issues. 
        4. The improved template should be a complete, ready-to-use prompt

        Critique Analysis: 
        <critique_feedbacks>
        ${critique_feedbacks}
        </critique_feedbacks>

        When you output JSON, ALWAYS 
        Return your response in this exact JSON format, start with 
        ```json
        {
            "root_cause": "Provide the root cause analysis from the feedbacks, please details Error Pattern Analysis and Root Cause Investigation, String FORMAT",
            "improved_template": "Provide the complete new template here with all recommended changes incorporated. This should be a fully functional template ready for the next iteration. String FORMAT"
        }

        IMPORTANT: The improved_template must be improved veresion o fCurrent Template by incorperating the recommended changes. PLEASE KEEP THE improved_template CONCISE AND EFFECTIVE.
        """
        
        # Initialize Bedrock client
        config = Config(
            connect_timeout=300,
            read_timeout=300
        )
        self.bedrock_runtime = boto3.client(service_name='bedrock-runtime', config=config)
        
    def call_bedrock_converse(self, prompt, temperature=0.1, top_p=0.9, max_tokens=2048):
        """
        Call Amazon Bedrock using the Converse API
        
        Args:
            prompt (str): The prompt to send to the model
            temperature (float): Controls randomness (0-1)
            top_p (float): Limits token selection to top P options
            max_tokens (int): Maximum tokens to generate
            
        Returns:
            str: The model's response text
        """
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
            "topP": top_p,
            "maxTokens": max_tokens
        }
        
        # Make the API call
        response = self.bedrock_runtime.converse(
            modelId=self.model_id,
            messages=messages,
            inferenceConfig=inference_config
        )
        
        # Extract the generated text from the response
        content_blocks = response["output"]["message"]["content"]
        for block in content_blocks:
            if "text" in block:
                return block["text"]
        
        return ""
    
    def generate_improvement_prompt(self, current_template, critique_feedbacks):
        """
        Generate a prompt for template improvement
        
        Args:
            current_template (str): The current prompt template
            critique_feedbacks (str): Feedback from the critique
            
        Returns:
            str: The generated improvement prompt
        """
        template = Template(self.guidance_prompt_improvement_template)
        improvement_prompt = template.safe_substitute(
            input_current_template=current_template,
            critique_feedbacks=critique_feedbacks
        )
        return improvement_prompt
    
    def improving_prompt_with_feedback(self, current_template, critique_feedbacks, 
                                      temperature=0.1, top_p=0.9, max_tokens=2048):
        """
        Improve a prompt template based on critique feedback
        
        Args:
            current_template (str): The current prompt template
            critique_feedbacks (str): Feedback from the critique
            temperature (float): Controls randomness (0-1)
            top_p (float): Limits token selection to top P options
            max_tokens (int): Maximum tokens to generate
            
        Returns:
            dict: The improvement results with analysis, recommendations, and improved template
        """
        
        improvement_prompt = self.generate_improvement_prompt(current_template, critique_feedbacks)
        
        improvement_results = {}
        
        try:
            # Call the Bedrock Converse API
            generated_text = self.call_bedrock_converse(
                prompt=improvement_prompt,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens
            )
                        
            # Use the imported function to parse the JSON result
            results_llm = load_json_from_llm_result(generated_text)
            
            # Create result entry
            if results_llm:
                improvement_results = {
                    "root_cause": results_llm.get("root_cause", ""),
                    "improved_template": results_llm.get("improved_template", "")
                }
            else:
                print("Failed to parse improvement results from model response")
                
        except Exception as e:
            print(f"Error in improving prompt: {e}")
        
        return improvement_results
