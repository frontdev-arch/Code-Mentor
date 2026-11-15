def count_long_words(words, min_length):
    """Return how many words have at least min_length characters."""
    count = 0
    for word in words:
        if len(word) >= min_length:
            count += 1
    return count
