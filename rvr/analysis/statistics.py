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
    Get user's personal stats
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
        games = [game for game in games if not _game_timed_out(session, game)]
        grand_total = 0.0 - situation.pot_pre
        total_played = 0
        for player in situation.players:
            # TODO: REVISIT: could iterate over games only once
            results = []
            for game in games:
                ev = _get_ev(game=game, order=player.order,
                             userid=userid)
                if ev is not None:
                    results.append(ev)
            total = sum(results)
            # Note: this is user's stddev for this position, not position's
            # stddev - because user having a different style of play can
            # make a difference to stddev. We have ddof=1 to help make up
            # for the smaller sample size.
            ddof = 1
            if len(results) > ddof + 1:
                user_stddev = numpy.std(results, ddof=ddof)
                confidence = _calculate_confidence(
                    total_result=total,
                    num_games=len(results),
                    be_mean=player.average_result,
                    stddev=user_stddev)
            else:
                confidence = 0.5  # they either are, or they aren't
            position_results.append(PositionResult(
                name=player.name,
                ev=player.average_result,
                stddev=player.stddev,  # site stddev okay?
                played=len(results),
                total=total if results else None,
                average=total / len(results) if results else None,
                confidence=confidence))
            if results and grand_total is not None:
                grand_total += total / len(results)
                grand_total -= player.contributed
            else:
                grand_total = None
            total_played += len(results)
        if total_played >= min_hands:
            situation_results.append(SituationResult(
                name=situation.description,
                average=grand_total,
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
