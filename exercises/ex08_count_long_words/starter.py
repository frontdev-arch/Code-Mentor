def count_long_words(words, min_length):
    """Return how many words have at least min_length characters."""
    for word in words:
        count = 0
        if len(word) >= min_length:
            count += 1
    return count
