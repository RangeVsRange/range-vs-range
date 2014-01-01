"""
Range-oriented poker functionality
"""
from rvr.infrastructure.util import concatenate

def _cmp_options(first, second):
    """
    Compare unweighted options
    """
    return cmp(sorted(first), sorted(second))

def _cmp_weighted_options(first, second):
    """
    Compare weighted options
    """
    return _cmp_options(first[0], second[0]) or cmp(first[1], second[1])

def _option_to_text(option):
    """
    option is set of two Card
    return something like "AhAd" (highest card first)
    """
    return "".join([o.ro_mnemonic() for o in sorted(option, reverse=True)])

def range_sum_equal(fold_range, passive_range, aggressive_range,
                    original_range):
    """
    Does fold + passive + aggressive = original?
    
    Each argument should be a HandRange

    Returns validity (boolean), and reason (string, or None if valid)
    """
    try:
        original_hand_options = original_range.generateOptions()
        all_ranges_hand_options = concatenate([r.generateOptions()
            for r in [fold_range, passive_range, aggressive_range]])
    except ValueError:
        return False, "invalid range description"
    original_hand_options.sort(cmp=_cmp_weighted_options)
    all_ranges_hand_options.sort(cmp=_cmp_weighted_options)
    prev = (None, -1)
    # There's no simple alternative to map(None, ...) pylint:disable=W0141
    for ori, new in map(None, original_hand_options, all_ranges_hand_options):
        # we compare two hands, each of which is a set of two Card
        if ori != new:
            # actually three scenarios:
            # hand is in multiple action ranges
            #     (new is the same as the previous new) 
            # hand is in action ranges but not original range
            #     (new < ori means new is not in original range)
            # hand is in original range but not action ranges
            #     (new > ori means ori is not in action ranges)
            if new is None:
                message =  \
                    "hand in original range but not in action ranges: %s" %  \
                    _option_to_text(ori[0])
            elif ori is None:
                message =  \
                    "hand in action ranges but not in original range: %s" %  \
                    _option_to_text(new[0])
            else:
                newh, neww = new
                orih, oriw = ori
                if newh == prev[0]:
                    message = "hand in multiple ranges: %s" %  \
                        _option_to_text(newh)
                elif _cmp_options(newh, orih) > 0:
                    message = "hand in original range but not in " +  \
                        "action ranges: %s" % _option_to_text(orih)
                elif _cmp_options(newh, orih) < 0:
                    message = "hand in action ranges but not in " +  \
                        "original range: %s" % _option_to_text(newh)
                elif neww != oriw:
                    message = "weight changed from %d to %d for hand %s" %  \
                        (oriw, neww, _option_to_text(orih))
                else:
                    raise RuntimeError("hands not equal, but can't " +  \
                                       "figure out why: %s, %s" % \
                                       (_option_to_text(orih),
                                        _option_to_text(newh)))
            return False, message
        prev = new
    return True, None
