def letter_grade(score):
    """Return 'A' for 70 and above, 'B' for 60-69, 'C' for 50-59 and 'F' below 50."""
    if score >= 70:
        return "A"
    elif score >= 60:
        return "B"
    elif score >= 50:
        return "C"
    else:
        return "F"
