from pathlib import Path

METRICS_FILE = "/app/metrics/axm1-llm-{0}-metrics.prom"

def write_metrics(model_name: str, duration: float, response: str):
    """Writes Prometheus-compatible metrics for Node Exporter."""
    token_count = len(response.split())
    tps = token_count / duration if duration > 0 else 0
    metrics = [
        f"# HELP axm1_llm_inference_{model_name}_duration_seconds LLM inference duration",
        f"# TYPE axm1_llm_inference_{model_name}_duration_seconds gauge",
        f"axm1_llm_inference_{model_name}_duration_seconds {duration:.3f}",
        f"# HELP axm1_llm_inference_{model_name}_tokens_generated Output tokens",
        f"# TYPE axm1_llm_inference_{model_name}_tokens_generated gauge",
        f"axm1_llm_inference_{model_name}_tokens_generated {token_count}",
        f"# HELP axm1_llm_inference_{model_name}_tokens_per_second Token throughput",
        f"# TYPE axm1_llm_inference_{model_name}_tokens_per_second gauge",
        f"axm1_llm_inference_{model_name}_tokens_per_second {tps:.3f}"
    ]

    Path(METRICS_FILE.format(model_name)).write_text("\n".join(metrics))
