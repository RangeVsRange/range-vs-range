"""
Handy things
"""
import itertools

def concatenate(list_of_lists):
    """
    Concatenate list of lists into list.
    """
    return list(itertools.chain.from_iterable(list_of_lists))