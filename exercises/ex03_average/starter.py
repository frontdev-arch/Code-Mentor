def average(scores):
    """Return the mean of a list of numbers. Return 0.0 for an empty list."""
    total = 0
    for s in scores:
        total += s
    return total / len(scores)
