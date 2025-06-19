#!/usr/bin/env python3

from strands import Agent
from strands_tools import http_request
from strands.telemetry.tracer import get_tracer
from strands.models import BedrockModel
from opentelemetry.sdk.trace import SpanProcessor
import logging
import os
from metrics_utils import save_metrics

# Set the environment variables for Sampling and Trace log correlation
os.environ["OTEL_RESOURCE_ATTRIBUTES"] = "aws.log.group.names=strands-agent-logs"
os.environ["OTEL_TRACES_SAMPLER"] = "always_on"
os.environ["OTEL_TRACES_SAMPLER_ARG"] = "1.0"

# Configure the tracer
tracer = get_tracer(
    service_name="weather-forecaster-strands-agent",
    otlp_endpoint="http://localhost:4316/v1/traces",
    otlp_headers={"Authorization": "Bearer TOKEN"},
)

# Configure the strands logger
strands_logger = logging.getLogger("strands")
strands_logger.setLevel(logging.INFO)  # Set to INFO or DEBUG to see more logs

# Create a file handler with proper formatting
file_handler = logging.FileHandler("strands_agents_sdk.log")
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s %(levelname)s [%(name)s] - %(message)s"
))

# Add the handler to the strands logger
strands_logger.addHandler(file_handler)

# Create a global variable to store the current trace ID
current_trace_id = None

# Custom span processor that captures trace ID 
class LoggingSpanProcessor(SpanProcessor):
    def on_start(self, span, parent_context=None):
        global current_trace_id
        # Get the hex representation of the trace ID
        current_trace_id = format(span.context.trace_id, 'x')
        
    def on_end(self, span):
        global current_trace_id
        # Get the hex representation of the trace ID
        current_trace_id = format(span.context.trace_id, 'x')
        
    def shutdown(self):
        pass

    def force_flush(self, timeout_millis=30000):
        pass

# Create and add the logging span processor
tracer.tracer_provider.add_span_processor(
    LoggingSpanProcessor()
)

# Define a weather-focused system prompt
WEATHER_SYSTEM_PROMPT = """You are a weather assistant with HTTP capabilities. You can:

1. Make HTTP requests to the National Weather Service API
2. Process and display weather forecast data
3. Provide weather information for locations in the United States

When retrieving weather information:
1. First get the coordinates or grid information using https://api.weather.gov/points/{latitude},{longitude} or https://api.weather.gov/points/{zipcode}
2. Then use the returned forecast URL to get the actual forecast

When displaying responses:
- Format weather data in a human-readable way
- Highlight important information like temperature, precipitation, and alerts
- Handle errors appropriately
- Convert technical terms to user-friendly language

Always explain the weather conditions clearly and provide context for the forecast.
"""

# Create a Bedrock model
bedrock_model = BedrockModel(
    model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    region_name="us-east-1" #region will be replaced by EC2 instance launch region during the setup
)

# Create an agent with HTTP capabilities (tracing will be enabled automatically)
weather_agent = Agent(
    model=bedrock_model,
    system_prompt=WEATHER_SYSTEM_PROMPT,
    tools=[http_request],
    # Add custom attributes for tracking
    trace_attributes={
        "session.id": "abc-1234",
        "user.id": "demo@example.com",
        "tags": [
            "Python-AgentSDK",
            "Observability-Tags",
            "CloudWatch-Demo"
        ]
    },  
)

# Example usage
if __name__ == "__main__":
    print("\nWeather Forecaster Strands Agent\n")
    print("This example demonstrates using Strands Agents' HTTP request capabilities")
    print("to get weather forecasts from the National Weather Service API.")
    print("\nOptions:")
    print("  'demo weather' - Demonstrate weather API capabilities")
    print("  'exit' - Exit the program")
    print("\nOr simply ask about the weather in any US location:")
    print("  'What's the weather like in San Francisco?'")
    print("  'Will it rain tomorrow in Miami?'")

    # Interactive loop
    while True:
        try:
            user_input = input("\n> ")

            if user_input.lower() == "exit":
                print("\nGoodbye! 👋")
                break

            # Call the weather agent
            response = weather_agent(user_input)
            
            # If using in conversational context, the response is already displayed
            # This is just for demonstration purposes
            print(str(response))
            
            # Log the entire response as a single entry
            formatted_response = str(response).replace('\n', ' ')

            # Inject trace_id for Trace to Log correlation
            strands_logger.info(f"trace_id={current_trace_id} {formatted_response}")

            # Get metrics summary
            metrics_summary = response.metrics.get_summary()
            
            # Save metrics to file in EMF format
            metrics_file = save_metrics(metrics_summary)
             
        except KeyboardInterrupt:
            print("\n\nExecution interrupted. Exiting...")
            break
        except Exception as e:
            print(f"\nAn error occurred: {str(e)}")
            print("Please try a different request.")
