"""
Handy things
"""
import itertools

def concatenate(list_of_lists):
    """
    Concatenate list of lists into list.
    """
    return list(itertools.chain.from_iterable(list_of_lists))

def stddev_one(prob):
    """
    Standard deviation of one event with a probability of prob
    """
    return (prob * (1 - prob) * (1 - prob) + (1 - prob) * prob * prob) ** 0.5