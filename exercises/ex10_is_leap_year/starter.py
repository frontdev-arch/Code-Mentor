def is_leap_year(year):
    """Return True if year is a leap year.
    A year is a leap year if it is divisible by 4, except years divisible by 100,
    which are leap years only if they are also divisible by 400."""
    return year % 4 == 0 and year % 100 != 0
