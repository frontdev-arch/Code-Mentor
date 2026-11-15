def sum_to_n(n):
    """Return the sum of the whole numbers from 1 to n inclusive. Return 0 when n is 0."""
    total = 0
    for i in range(1, n + 1):
        total += i
    return total
