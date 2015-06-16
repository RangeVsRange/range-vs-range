"""
Handy things
"""
import itertools
from flask.ctx import copy_current_request_context
from threading import Thread

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

def on_a_different_thread(fun):
    """
    Invoke fun on a different thread.
    
    Per http://stackoverflow.com/questions/11047307/
        run-flask-mail-asynchronously/18407455
    """
    def wrapped():
        thr = Thread(target=copy_current_request_context(fun))
        thr.start()

    return wrapped
