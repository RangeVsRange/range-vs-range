from rvr.db import tables
from rvr.local_settings import SUPPRESSED_GAME_MAX, SUPPRESSED_SITUATIONS
import numpy
from rvr.core.dtos import PositionResult, SituationResult
import math
from scipy import stats
import logging

def _calculate_confidence(total_result, num_games,
                          be_mean, stddev):
    """
    total_result is the user's total chips won in a position.

    num_games is the number of games over which the user has won these chips.

    be_mean is the expected result for a breakeven player playing one game in
    this position.

    stddev is the standard deviation for this position.

    Returns a confidence rating between 0.0 and 1.0. This should be interpreted
    as follows:
        "If you are a breakeven player, you are in the luckiest
         ((1 - confidence) * 100)% of players on the site."

    Mathematically, what is the chance of a variable with given mean and stddev
    when summed over N trials being less than the given total?

    Well if X has mean M and std S, then N*X has mean N*M and std sqrt(N)*S
    """
    # pylint:disable=no-member
    if num_games == 0:
        return 0.5
    be_total = be_mean * num_games
    be_stddev = stddev * math.sqrt(num_games)
    if be_stddev == 0.0:  # too few games
        if total_result > be_total:
            return 1.0
        elif total_result < be_total:
            return 0.0
        else:
            return 0.5  # now that's just silly!
    # the following is what the average player's results total looks like after
    # num_games games
    be_norm = stats.norm(loc=be_total, scale=be_stddev)
    return be_norm.cdf(total_result)

def _get_ev(game, order, userid):
    """
    Return user's 'ev' result, or None
    """
    for rgp in game.rgps:
        if rgp.order == order and rgp.userid == userid:
            for result in rgp.results:
                if result.scheme == 'ev':
                    return result.result
    return None

def _game_timed_out(session, game):
    """
    Did this game time out?
    """
    return session.query(tables.GameHistoryTimeout)  \
        .filter(tables.GameHistoryTimeout.gameid == game.gameid)  \
        .count() > 0

def get_user_statistics(session, userid, min_hands, is_competition):
    """
    Get user's personal stats for all situations
    """
    # pylint:disable=no-member
    all_situations = session.query(tables.Situation).all()
    # For now, there are only situation-specific results (nothing global).
    situation_results = []
    for situation in all_situations:
        if situation.situationid in SUPPRESSED_SITUATIONS:
            continue
        if any(player.average_result is None
               for player in situation.players):
            # This can happen before global analysis is run.
            # Suppress situation for now.
            continue
        position_results = []
        games = session.query(tables.RunningGame)  \
            .filter(tables.RunningGame.public_ranges != is_competition)  \
            .filter(tables.RunningGame.situationid ==
                    situation.situationid)  \
            .filter(tables.RunningGame.gameid > SUPPRESSED_GAME_MAX)  \
            .all()
        groups = {}
        for game in games:
            groups.setdefault(game.spawn_group, []).append(game)
        for spawn_group in groups.keys():
            if any(not g.game_finished or _game_timed_out(session, g)
                   for g in groups[spawn_group]):
                groups.pop(spawn_group)
        orbit_average = 0.0 - situation.pot_pre
        total_played = 0
        for player in situation.players:
            results = {}
            for spawn_group, games in groups.iteritems():
                for game in games:
                    ev = _get_ev(game=game, order=player.order,
                                 userid=userid)
                    if ev is None:  # they didn't play this position
                        continue
                    results.setdefault(spawn_group, 0.0)
                    results[spawn_group] += ev * game.spawn_factor
            data = filter(lambda x: x is not None, results.values())
            total = sum(data)
            confidence = _calculate_confidence(
                total_result=total,
                num_games=len(data),
                be_mean=player.average_result,
                stddev=player.stddev)  # population stats are more reliable
            position_results.append(PositionResult(
                situationid=situation.situationid,
                order=player.order,
                name=player.name,
                ev=player.average_result,  # situation ev
                stddev=player.stddev,  # population stats are more reliable
                played=len(data),
                total=total if data else None,
                average=total / len(data) if data else None,
                confidence=confidence))
            if data and orbit_average is not None:
                orbit_average += total / len(data)
                orbit_average -= player.contributed
            else:
                orbit_average = None
            total_played += len(data)
        if total_played >= min_hands:
            situation_results.append(SituationResult(
                situationid=situation.situationid,
                name=situation.description,
                average=orbit_average,
                positions=position_results))
    return situation_results

def recalculate_global_statistics(session):
    """
    Calculate situation players' averages
    """
    suppressed_game_ids = set([h.gameid for h in  \
                              session.query(tables.GameHistoryTimeout).all()])
    logging.debug('%d timed-out games suppressed', len(suppressed_game_ids))
    positions = session.query(tables.SituationPlayer).all()
    for position in positions:
        results = []
        # TODO: REVISIT: This is inefficient. Query RunningGame first...
        # ... then use game.rgps.
        rgps = session.query(tables.RunningGameParticipant)  \
            .filter(tables.RunningGameParticipant.gameid >
                    SUPPRESSED_GAME_MAX)  \
            .filter(tables.RunningGameParticipant.order == position.order) \
            .all()
        # Note: we're only including competition mode - because it's more
        # popular. We can't include both (unless we track them separately).
        # Optimisation mode would be a better estimator, but we'd have to
        # calculate over groups, not games, because optimisation mode makes
        # rare lines more likely - it makes them 100% likely.
        for rgp in [r for r in rgps
                    if r.game.situationid == position.situationid
                    and not r.game.public_ranges
                    and r.gameid not in suppressed_game_ids]:
            for result in rgp.results:
                if result.scheme == 'ev':
                    results.append(result.result)
        if results:
            position.average_result = sum(results) / len(results)
            position.stddev = numpy.std(results)  # pylint:disable=no-member
        else:
            position.average_result = None
            position.stddev = None
        logging.debug('situationid %d (%s), position %d (%s), '
            'average_result %r (stddev %r) over %d games',
            position.situationid, position.situation.description,
            position.order, position.name, position.average_result,
            position.stddev, len(results))
