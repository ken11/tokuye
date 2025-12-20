import threading
import time
from typing import Dict, List, Tuple

from tokuye.utils.config import settings

MODEL_COST = {
    "sonnet-4": {
        "input": 0.003,
        "output": 0.015,
        "cache_write": 0.00375,
        "cache_read": 0.0003,
    },
    "sonnet-4-5": {
        "input": 0.003,
        "output": 0.015,
        "cache_write": 0.00375,
        "cache_read": 0.0003,
    },
    "haiku-4-5": {
        "input": 0.001,
        "output": 0.005,
        "cache_write": 0.00125,
        "cache_read": 0.0001,
    },
    "opus-4-5": {
        "input": 0.005,
        "output": 0.025,
        "cache_write": 0.00625,
        "cache_read": 0.0005,
    },
}


class TokenUsageTracker:
    """
    Tracks token usage across multiple LLM calls within a single conversation turn
    and maintains session-wide totals.
    Thread-safe implementation to handle concurrent access.
    """

    EMBEDDING_TOKEN_PRICE = 0.000029  # USD per 1000 tokens (for Titan Embeddings)

    # Exchange rate (JPY per USD)
    EXCHANGE_RATE = 155

    def __init__(self):
        self._lock = threading.Lock()
        # Token usage for current turn
        self._current_turn_usage: Dict[str, int] = self._create_empty_usage_dict()

        # Token usage for entire session
        self._session_usage: Dict[str, int] = self._create_empty_usage_dict()

        # History log (with timestamps)
        self._usage_history: List[Tuple[float, Dict[str, int]]] = []

    def set_cost_table(self):
        self.cost_table = MODEL_COST[settings.model_identifier]

    def _create_empty_usage_dict(self) -> Dict[str, int]:
        """Create empty token usage dictionary"""
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_tokens": 0,
            "cache_read_tokens": 0,
            "embedding_tokens": 0,
            "repo_desc_input_tokens": 0,
            "repo_desc_output_tokens": 0,
        }

    def reset_turn(self):
        """Reset token counters for a new conversation turn."""
        with self._lock:
            # Add current turn usage to history (only if tokens were used)
            if sum(self._current_turn_usage.values()) > 0:
                self._usage_history.append(
                    (time.time(), self._current_turn_usage.copy())
                )

            # Reset counters for new turn
            self._current_turn_usage = self._create_empty_usage_dict()

    def add_usage(self, usage: Dict):
        """
        Add token usage from a single LLM call to the current turn total
        and session total.

        Args:
            usage_metadata: Token usage metadata from LLM response
        """
        with self._lock:
            input_tokens = usage.get("inputTokens", 0)
            output_tokens = usage.get("outputTokens", 0)

            # Update current turn usage
            self._current_turn_usage["input_tokens"] += input_tokens
            self._current_turn_usage["output_tokens"] += output_tokens

            # Also update session-wide usage
            self._session_usage["input_tokens"] += input_tokens
            self._session_usage["output_tokens"] += output_tokens

            cache_creation = usage.get("cacheWriteInputTokens", 0)
            cache_read = usage.get("cacheReadInputTokens", 0)

            # Update current turn usage
            self._current_turn_usage["cache_creation_tokens"] += cache_creation
            self._current_turn_usage["cache_read_tokens"] += cache_read

            # Also update session-wide usage
            self._session_usage["cache_creation_tokens"] += cache_creation
            self._session_usage["cache_read_tokens"] += cache_read

    def add_embedding_usage(self, token_count: int):
        """
        Add embedding token usage to the current turn total and session total.

        Args:
            token_count: Number of tokens used for embedding
        """
        with self._lock:
            self._current_turn_usage["embedding_tokens"] += token_count
            self._session_usage["embedding_tokens"] += token_count

    def add_repo_description_usage(self, input_tokens: int, output_tokens: int):
        """
        Add repository description generation token usage to the current turn total and session total.

        Args:
            input_tokens: Number of input tokens for repo description
            output_tokens: Number of output tokens for repo description
        """
        with self._lock:
            # Update current turn usage
            self._current_turn_usage["repo_desc_input_tokens"] += input_tokens
            self._current_turn_usage["repo_desc_output_tokens"] += output_tokens
            self._current_turn_usage["input_tokens"] += input_tokens
            self._current_turn_usage["output_tokens"] += output_tokens

            # Also update session-wide usage
            self._session_usage["repo_desc_input_tokens"] += input_tokens
            self._session_usage["repo_desc_output_tokens"] += output_tokens
            self._session_usage["input_tokens"] += input_tokens
            self._session_usage["output_tokens"] += output_tokens

    def get_turn_usage(self) -> Dict[str, int]:
        """Get the current turn's total token usage."""
        with self._lock:
            return self._current_turn_usage.copy()

    def calculate_cost(self, token_count: int, price_per_1k: float) -> float:
        """
        Calculate cost for given token count and price per 1000 tokens.

        Args:
            token_count: Number of tokens
            price_per_1k: Price per 1000 tokens in USD

        Returns:
            Cost in USD
        """
        return (token_count / 1000) * price_per_1k

    def get_total_cost(self) -> float:
        """
        Get cumulative cost for entire session in Japanese Yen

        Returns:
            Cumulative cost (Japanese Yen)
        """
        with self._lock:
            usage = self._session_usage

            # Calculate cost for each token type (USD)
            input_cost = self.calculate_cost(
                usage["input_tokens"], self.cost_table["input"]
            )
            output_cost = self.calculate_cost(
                usage["output_tokens"], self.cost_table["output"]
            )

            # Cache cost
            cache_creation_cost = self.calculate_cost(
                usage["cache_creation_tokens"], self.cost_table["cache_write"]
            )
            cache_read_cost = self.calculate_cost(
                usage["cache_read_tokens"], self.cost_table["cache_read"]
            )

            # Embedding cost
            embedding_cost = self.calculate_cost(
                usage["embedding_tokens"], self.EMBEDDING_TOKEN_PRICE
            )

            # Total cost (USD)
            total_cost_usd = (
                input_cost
                + output_cost
                + cache_creation_cost
                + cache_read_cost
                + embedding_cost
            )

            if settings.language == "en":
                return total_cost_usd

            # Convert to JPY
            total_cost_jpy = total_cost_usd * self.EXCHANGE_RATE

            return total_cost_jpy

    def format_total_cost_jpy(self) -> str:
        """
        Get cumulative cost for entire session formatted in Japanese Yen

        Returns:
            Formatted cumulative cost (e.g., "¥123円")
        """
        total_cost = self.get_total_cost()
        if settings.language == "en":
            return f"[bold yellow]💰 Estimated cost: ${total_cost:.2f}[/]\nThis amount is an estimate for ap-northeast-1.\nAccuracy is not guaranteed."
        return f"[bold yellow]💰 コスト概算: ¥{total_cost:.2f}[/]\n金額はap-northeast-1における目安です\n正確性を保証するものではありません"

    def _format_usage_details(self, usage: Dict[str, int]) -> str:
        """
        Format usage details for display.

        Args:
            usage: Token usage dictionary

        Returns:
            Formatted string with usage details
        """
        total = usage["input_tokens"] + usage["output_tokens"]

        # Calculate cost for each token type (USD)
        input_cost = self.calculate_cost(usage["input_tokens"], self.cost_table["input"])
        output_cost = self.calculate_cost(
            usage["output_tokens"], self.cost_table["output"]
        )
        total_cost = input_cost + output_cost

        # Convert to JPY
        total_cost_jpy = total_cost * self.EXCHANGE_RATE

        details = f"{total:,} total ({usage['input_tokens']:,} input + {usage['output_tokens']:,} output)"
        details += f" | Cost: ${total_cost:.6f} (¥{total_cost_jpy:.2f})"

        # Add cache information if available
        if usage["cache_creation_tokens"] > 0 or usage["cache_read_tokens"] > 0:
            cache_creation_cost = self.calculate_cost(
                usage["cache_creation_tokens"], self.cost_table["cache_write"]
            )
            cache_read_cost = self.calculate_cost(
                usage["cache_read_tokens"], self.cost_table["cache_read"]
            )
            cache_total_cost = cache_creation_cost + cache_read_cost
            cache_total_cost_jpy = cache_total_cost * self.EXCHANGE_RATE

            details += f"\n   Cache: {usage['cache_creation_tokens']:,} created, {usage['cache_read_tokens']:,} read"
            details += (
                f" | Cache Cost: ${cache_total_cost:.6f} (¥{cache_total_cost_jpy:.2f})"
            )

        # Add embedding token information if available
        if usage["embedding_tokens"] > 0:
            embedding_cost = self.calculate_cost(
                usage["embedding_tokens"], self.EMBEDDING_TOKEN_PRICE
            )
            embedding_cost_jpy = embedding_cost * self.EXCHANGE_RATE

            details += f"\n   Embeddings: {usage['embedding_tokens']:,} tokens"
            details += (
                f" | Embedding Cost: ${embedding_cost:.6f} (¥{embedding_cost_jpy:.2f})"
            )

        # Add repository description generation information if available
        if usage["repo_desc_input_tokens"] > 0 or usage["repo_desc_output_tokens"] > 0:
            repo_desc_input_cost = self.calculate_cost(
                usage["repo_desc_input_tokens"], self.cost_table["input"]
            )
            repo_desc_output_cost = self.calculate_cost(
                usage["repo_desc_output_tokens"], self.cost_table["output"]
            )
            repo_desc_total_cost = repo_desc_input_cost + repo_desc_output_cost
            repo_desc_total_cost_jpy = repo_desc_total_cost * self.EXCHANGE_RATE

            details += f"\n   Repo Description: {usage['repo_desc_input_tokens']:,} input, {usage['repo_desc_output_tokens']:,} output"
            details += f" | Repo Description Cost: ${repo_desc_total_cost:.6f} (¥{repo_desc_total_cost_jpy:.2f})"

        return details

    def format_usage_summary(self) -> str:
        """Format a human-readable summary of token usage for the current turn."""
        usage = self.get_turn_usage()
        return f"📊 Turn Token Usage: {self._format_usage_details(usage)}"

    def format_usage_history(self, max_entries: int = 10) -> str:
        """
        Format the usage history as a log.

        Args:
            max_entries: Maximum number of history entries to include

        Returns:
            Formatted history log
        """
        with self._lock:
            if not self._usage_history:
                return "No usage history available."

            # Get specified number of entries from most recent
            recent_history = self._usage_history[-max_entries:]

            lines = ["📜 Token Usage History:"]
            for timestamp, usage in recent_history:
                # Format timestamp
                time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))

                # Total token count and breakdown
                total = usage["input_tokens"] + usage["output_tokens"]

                # Calculate cost
                input_cost = self.calculate_cost(
                    usage["input_tokens"], self.cost_table["input"]
                )
                output_cost = self.calculate_cost(
                    usage["output_tokens"], self.cost_table["output"]
                )
                total_cost = input_cost + output_cost
                total_cost_jpy = total_cost * self.EXCHANGE_RATE

                # Add entry
                lines.append(f"[{time_str}] {total:,} tokens (¥{total_cost_jpy:.2f})")

            return "\n".join(lines)


# Global instance for tracking token usage across the application
token_tracker = TokenUsageTracker()
