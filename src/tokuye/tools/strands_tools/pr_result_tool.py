_last_pr_result: bool = False


def report_pr_result(has_issue: bool) -> None:
    """Report the result of the PR creation phase.
    
    Args:
        has_issue: Whether there was an issue during PR creation.
    """
    global _last_pr_result
    _last_pr_result = has_issue


def get_last_pr_result() -> bool:
    """Get the last reported PR result.
    
    Returns:
        The last reported PR result.
    """
    return _last_pr_result


def reset_last_pr_result() -> None:
    """Reset the last PR result to the default value."""
    global _last_pr_result
    _last_pr_result = False