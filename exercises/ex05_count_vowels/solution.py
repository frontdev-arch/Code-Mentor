def count_vowels(text):
    """Return how many vowels (a, e, i, o, u, in either case) are in text."""
    count = 0
    for i in range(len(text)):
        if text[i].lower() in "aeiou":
            count += 1
    return count
