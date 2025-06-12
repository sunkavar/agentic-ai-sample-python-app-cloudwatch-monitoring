#!/usr/bin/env python3

import json
import time
import os

def extract_metrics(metrics_summary):
    """
    Extract key metrics from the agent's metrics summary and format them as EMF.
    
    Args:
        metrics_summary (dict): The metrics summary from agent.metrics.get_summary()
        
    Returns:
        dict: EMF-formatted metrics
    """
    # Extract the requested metrics
    emf_metrics = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),  # Current time in milliseconds
            "LogGroupName": "strands-agent-metrics",  # Required for CloudWatch agent to know which log group to use
            "CloudWatchMetrics": [{
                "Namespace": "StrandsAgentMetrics",
                "Dimensions": [["AgentName"]],
                "Metrics": [
                    {"Name": "LatencyMs", "Unit": "Milliseconds"},
                    {"Name": "InputTokens", "Unit": "Count"},
                    {"Name": "OutputTokens", "Unit": "Count"},
                    {"Name": "ToolCallCount", "Unit": "Count"},
                    {"Name": "ErrorCount", "Unit": "Count"},
                    {"Name": "SuccessCount", "Unit": "Count"},
                    {"Name": "SuccessRate", "Unit": "None"},
                    {"Name": "TotalCycles", "Unit": "Count"},
                    {"Name": "TotalDuration", "Unit": "Seconds"}
                ]
            }]
        },
        "AgentName": "weather-forecaster-strands-agent",
        "LatencyMs": metrics_summary.get("accumulated_metrics", {}).get("latencyMs", 0),
        "InputTokens": metrics_summary.get("accumulated_usage", {}).get("inputTokens", 0),
        "OutputTokens": metrics_summary.get("accumulated_usage", {}).get("outputTokens", 0),
        "TotalCycles": metrics_summary.get("total_cycles", 0),
        "TotalDuration": metrics_summary.get("total_duration", 0)
    }
    
    # Extract tool usage metrics
    tool_usage = metrics_summary.get("tool_usage", {})
    call_count = 0
    error_count = 0
    success_count = 0
    success_rate = 0
    
    # Aggregate metrics across all tools
    for tool_name, tool_data in tool_usage.items():
        execution_stats = tool_data.get("execution_stats", {})
        call_count += execution_stats.get("call_count", 0)
        error_count += execution_stats.get("error_count", 0)
        success_count += execution_stats.get("success_count", 0)
    
    # Calculate success rate if there were any calls
    if call_count > 0:
        success_rate = success_count / call_count
    
    # Add tool metrics to EMF
    emf_metrics["ToolCallCount"] = call_count
    emf_metrics["ErrorCount"] = error_count
    emf_metrics["SuccessCount"] = success_count
    emf_metrics["SuccessRate"] = success_rate
    
    return emf_metrics

def save_metrics(metrics_summary, filename="strands_agent_metrics.json"):
    """
    Save the extracted metrics to a file in EMF format.
    
    Args:
        metrics_summary (dict): The metrics summary from agent.metrics.get_summary()
        filename (str): The name of the file to save the metrics to
    """
    emf_metrics = extract_metrics(metrics_summary)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)
    
    # Append metrics to file - ensure it's on a single line without newlines
    with open(filename, 'a') as f:
        # Use separators to ensure compact JSON with no extra spaces
        f.write(json.dumps(emf_metrics, separators=(',', ':')) + "\n")
    
    return filename