_last_planning_result: str = "response"


def report_planning_result(result_type: str) -> None:
    """Report the result type of the planning phase.
    
    Args:
        result_type: The type of result, either "plan" or "response".
    """
    global _last_planning_result
    _last_planning_result = result_type


def get_last_planning_result() -> str:
    """Get the last reported planning result type.
    
    Returns:
        The last reported planning result type.
    """
    return _last_planning_result


def reset_last_planning_result() -> None:
    """Reset the last planning result type to the default value."""
    global _last_planning_result
    _last_planning_result = "response"