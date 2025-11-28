import logging
import re
import threading
from pathlib import Path

METRICS_FILE = "/app/metrics/axm1-llm-{0}-metrics.prom"
AVG_TOKEN_PATTERN = re.compile("(avg)(.*)(token\/s$)")

logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.DEBUG)


class Metrics:

    def __init__(self):
        self.avg_token_per_second = None

    def write(self, model_name: str, duration: float, response: str):
        """Writes Prometheus-compatible metrics for Node Exporter."""
        try:
            # Extract the avg token/s from the llm (if present). And if not, calculate
            token_count = len(response.split())
            if self.avg_token_per_second:
                tps = self.avg_token_per_second
            else:
                tps = token_count / duration if duration > 0 else 0

            metrics = [
                f"# HELP axm1_llm_inference_{model_name}_duration_seconds LLM inference duration",
                f"# TYPE axm1_llm_inference_{model_name}_duration_seconds gauge",
                f"axm1_llm_inference_{model_name}_duration_seconds {duration:.2f}",
                f"# HELP axm1_llm_inference_{model_name}_tokens_generated Output tokens",
                f"# TYPE axm1_llm_inference_{model_name}_tokens_generated gauge",
                f"axm1_llm_inference_{model_name}_tokens_generated {token_count}",
                f"# HELP axm1_llm_inference_{model_name}_tokens_per_second Token throughput",
                f"# TYPE axm1_llm_inference_{model_name}_tokens_per_second gauge",
                f"axm1_llm_inference_{model_name}_tokens_per_second {tps:.2f}"
            ]
            Path(METRICS_FILE.format(model_name)).write_text("\n".join(metrics))
        except Exception as e:
            logger.error("Error while writing metrics!", repr(e))

    def process_llm_output(self, line):
        if line == None:
            return
        match = AVG_TOKEN_PATTERN.search(line)
        if match:
            self.avg_token_per_second = float(match.group(2).strip())
            logger.debug(f"Got avg-token line: {line}")
