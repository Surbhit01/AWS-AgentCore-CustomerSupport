"""Central configuration for the customer support agent."""
import logging

# Bedrock application inference profile ARN for the model in use.

MODEL_ID = ""
MODEL_PROVIDER = ""  # required for Bedrock inference profile ARNs

LOG_LEVEL = logging.INFO

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)

logger = logging.getLogger("customer_support_agent")
