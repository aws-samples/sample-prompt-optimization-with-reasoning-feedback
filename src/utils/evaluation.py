def evaluate_test_results(result_data):
    """
    Evaluate test results by comparing predictions with ground truth.
    
    Args:
        result_data (dict): Dictionary containing test cases and their results
        
    Returns:
        dict: Updated result_data with evaluation metrics
    """
    task_success = 0
    for index, test_case in enumerate(result_data['test_cases']):
        expected_output = test_case.get("ground_truth", "")
        llm_output = test_case.get("prediction", "")
        
        if expected_output == llm_output:
            task_success += 1
            result_data['test_cases'][index]['task_succeed'] = True
        else:
            result_data['test_cases'][index]['task_succeed'] = False
            
    result_data['stats']['task_succeed'] = task_success
    return result_data