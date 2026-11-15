def running_totals(numbers):
    """Return a list where each item is the sum of all numbers up to that position.
    For example, [1, 2, 3] gives [1, 3, 6]."""
    totals = []
    total = 0
    for n in numbers:
        total += n
        totals.append(total)
    return totals
