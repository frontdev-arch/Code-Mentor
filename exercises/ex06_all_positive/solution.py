def all_positive(numbers):
    """Return True if every number in the list is greater than zero, otherwise False.
    An empty list counts as True."""
    for n in numbers:
        if n <= 0:
            return False
    return True
