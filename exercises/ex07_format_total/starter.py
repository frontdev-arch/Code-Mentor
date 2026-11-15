def format_total(prices):
    """Return a string like 'Total: 7.5' giving the sum of a list of prices."""
    total = 0
    for p in prices:
        total += p
    return "Total: " + total
