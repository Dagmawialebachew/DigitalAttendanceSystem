# attendance/templatetags/custom_filters.py (Create this file)
from django import template

register = template.Library()

@register.filter
def to_int(value):
    """Converts a value to an integer, returning 0 on failure."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0