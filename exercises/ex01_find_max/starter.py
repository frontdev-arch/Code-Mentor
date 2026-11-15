def find_max(numbers):
    """Return the largest number in a non-empty list."""
    maximum = 0
    for n in numbers:
        if n > maximum:
            maximum = n
    return maximum
