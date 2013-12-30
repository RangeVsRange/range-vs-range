"""
Handy things
"""
import itertools

def concatenate(list_of_lists):
    return list(itertools.chain.from_iterable(list_of_lists))