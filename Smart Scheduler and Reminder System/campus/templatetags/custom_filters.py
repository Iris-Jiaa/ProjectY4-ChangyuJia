from django import template
from django.utils.timesince import timesince

register = template.Library()

@register.filter(name='custom_timesince')
def custom_timesince_filter(value):
    """ 
        This is function returns the value of time past since a scheduled lecture to the current date. If the time past is in: 
            - minutes, return 'm',
            - hours, return 'h', 
            - days, return 'd',
            - weeks, return 'w',
        
        If all the above conditions are false, i.e. time past is less than a minute, then return 'Just now'.

        - My main aim was to mimic how Instagram displays time past since a logged in user uploaded his/her post to their News Feed.
    """
    
    time_diff = timesince(value)    # time difference

    (time_diff := time_diff.split(',')[0])  # split time and access the first value.

    if 'minute' in time_diff:
        return f"{time_diff[:2]}m"     # get the first 2 items in the str. value
    
    elif 'hour' in time_diff:
        return f"{time_diff[:2]}h"
    
    elif 'day' in time_diff:
        return f"{time_diff[:2]}d"
    
    elif 'week' in time_diff:
        return f"{time_diff[:2]}w"
    
    else:
        return 'Just now'

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter(name='split')
def split_filter(value, arg=','):
    """Split a string by the given separator. {{ "a,b,c"|split:"," }} → ['a','b','c']"""
    return value.split(arg)


@register.filter(name='replace')
def replace_filter(value, arg):
    """
    Replaces all occurrences of a substring with another substring.
    Usage: {{ value|replace:"old_string|new_string" }}
    """
    if not isinstance(value, str) or not isinstance(arg, str):
        return value

    try:
        old, new = arg.split('|', 1)
    except ValueError:
        return value # Invalid argument format

    return value.replace(old, new)