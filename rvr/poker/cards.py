"""
Rank, Suit, Card classes and associated functionality
"""
import random

# pylint:disable=R0903

PREFLOP = "Preflop"
FLOP = "Flop"
TURN = "Turn"
RIVER = "River"

class Rank(object):
    """
    Represents a card rank
    """
    def __init__(self, singular, plural):
        self.singular = singular
        self.plural = plural
    def __str__(self):
        return self.singular
    def __repr__(self):
        return self.singular
    def __eq__(self, other):
        return self is other
    def __ne__(self, other):
        return not self.__eq__(other)
    def __cmp__(self, other):
        return cmp(RANKS_LOW_TO_HIGH.index(self),
                   RANKS_LOW_TO_HIGH.index(other))
    def __hash__(self):
        return hash(self.singular)
    @classmethod
    def from_mnemonic(cls, char):
        """
        From the relevant rank character, e.g. 'K' -> King 
        """
        return RANK_MAP[char]

class Suit(object):
    """
    Represents a card suit
    """
    def __init__(self, singular, text):
        self.singular = singular
        self.text = text
    def __str__(self):
        return self.text
    def __repr__(self):
        return self.text
    def __eq__(self, other):
        return self is other
    def __ne__(self, other):
        return not self.__eq__(other)
    def __cmp__(self, other):
        return cmp(SUITE_LOW_TO_HIGH.index(self),
                   SUITE_LOW_TO_HIGH.index(other))
    def __hash__(self):
        return hash(self.text)
    @classmethod
    def from_mnemonic(cls, char):
        """
        From the relevant suit character, e.g. 's' -> Spades
        """
        return SUIT_MAP[char]

ACE = Rank("Ace", "Aces")
KING = Rank("King", "Kings")
QUEEN = Rank("Queen", "Queens")
JACK = Rank("Jack", "Jacks")
TEN = Rank("Ten", "Tens")
NINE = Rank("Nine", "Nines")
EIGHT = Rank("Eight", "Eights")
SEVEN = Rank("Seven", "Sevens")
SIX = Rank("Six", "Sixes")
FIVE = Rank("Five", "Fives")
FOUR = Rank("Four", "Fours")
TREY = Rank("Three", "Threes")
DEUCE = Rank("Two", "Twos")

SPADES = Suit("Spade", "Spades")
HEARTS = Suit("Heart", "Hearts")
DIAMONDS = Suit("Diamond", "Diamonds")
CLUBS = Suit("Club", "Clubs")

RANKS_HIGH_TO_LOW = [ACE, KING, QUEEN, JACK, TEN, NINE, EIGHT, SEVEN, SIX,
                     FIVE, FOUR, TREY, DEUCE]
RANKS_LOW_TO_HIGH = list(reversed(RANKS_HIGH_TO_LOW))

SUITS_HIGH_TO_LOW = [SPADES, HEARTS, DIAMONDS, CLUBS]
SUITE_LOW_TO_HIGH = list(reversed(SUITS_HIGH_TO_LOW))

RANK_MAP = {
    "A": ACE,
    "K": KING,
    "Q": QUEEN,
    "J": JACK,
    "T": TEN,
    "9": NINE,
    "8": EIGHT,
    "7": SEVEN,
    "6": SIX,
    "5": FIVE,
    "4": FOUR,
    "3": TREY,
    "2": DEUCE
    }

RANK_INVERT = {v:k for k, v in RANK_MAP.items()}

SUIT_MAP = {
    "s": SPADES,
    "h": HEARTS,
    "d": DIAMONDS,
    "c": CLUBS
    }

SUIT_INVERT = {v:k for k, v in SUIT_MAP.items()}

RANK_FOR_MASK = {
    ACE: 12,
    KING: 11,
    QUEEN: 10,
    JACK: 9,
    TEN: 8,
    NINE: 7,
    EIGHT: 6,
    SEVEN: 5,
    SIX: 4,
    FIVE: 3,
    FOUR: 2,
    TREY: 1,
    DEUCE: 0
    }

SUIT_FOR_MASK = {
    SPADES: 3,
    HEARTS: 2,
    DIAMONDS: 1,
    CLUBS: 0
    }

class Card(object):
    """
    Represents a card, i.e. a rank and a suit
    """
    def __init__(self, rank, suit):
        if not isinstance(rank, Rank):
            raise TypeError("rank is not a Rank")
        if not isinstance(suit, Suit):
            raise TypeError("suit is not a Suit")
        self.rank = rank
        self.suit = suit

    @classmethod
    def from_text(cls, text):
        """
        null-coalescing
        """
        if len(text) != 2:
            raise ValueError("Invalid card mnemonic: '%s'" % text)
        rank, suit = text
        if rank not in RANK_MAP:
            raise ValueError("Invalid rank mnemonic: '%s'" % rank)
        if suit not in SUIT_MAP:
            raise ValueError("Invalid suit mnemonic: '%s'" % suit)
        return cls(RANK_MAP[rank], SUIT_MAP[suit])

    @classmethod
    def many_from_text(cls, text):
        """
        null-coalescing
        """
        if len(text) % 2 != 0:
            raise ValueError("Invalid card list: '%s'" % text)
        return [cls.from_text(text[i * 2:i * 2 + 2])
                for i in range(len(text) / 2)]

    def to_mnemonic(self):
        """
        Return a two-character representation of a card, e.g. "7c" for the Seven
        of Clubs.
        Note that HandRange relies on this format, so the return value of this
        method should not be changed without considering the impact on
        HandRange.
        """
        return RANK_INVERT[self.rank] + SUIT_INVERT[self.suit]
    
    def to_mask(self):
        """
        For calculations, convert to raw data mask
        """
        return 1 << (13 * SUIT_FOR_MASK[self.suit] + RANK_FOR_MASK[self.rank])

    def __str__(self):
        # Note: Suits are plurals, Ranks are singular.
        return "%s of %s" % (str(self.rank), str(self.suit))
    
    def __repr__(self):
        return self.__str__()
    
    def __cmp__(self, other):
        if not isinstance(other, Card):
            return 0
        return cmp(self.rank, other.rank) or cmp(self.suit, other.suit)
    
    def __eq__(self, other):
        if not isinstance(other, Card):
            return False
        return self.rank == other.rank and self.suit == other.suit
    
    def __ne__(self, other):
        return not self.__eq__(other)
    
    def __hash__(self):
        return hash(self.rank) ^ hash(self.suit)

def deal_card(excluded):
    """
    Warning! Dealt cards will be appended to excluded list!
    """
    deck = [Card(rank, suit)
            for rank in RANKS_HIGH_TO_LOW
            for suit in SUITS_HIGH_TO_LOW]
    for ex in excluded:
        deck.remove(ex)
    card = random.choice(deck)
    excluded.append(card)
    return card

def deal_cards(excluded, number):
    """
    Deal multiple cards and return as a list
    """
    return [deal_card(excluded) for _ in range(number)]

def main():
    """
    Test script
    """
    pairs = [
        ('Ah', 'Ac'),
        ('Ac', 'Ah'),
        ('Ah', 'Ah'),
        ('Ah', 'Ks'),
        ('Ah', 'Kh'),
        ('Ah', 'Kc')
        ]
    for pair in pairs:
        card1 = Card.from_text(pair[0])
        card2 = Card.from_text(pair[1])
        result = cmp(card1, card2)
        if not result:
            char = '='
        elif result < 0:
            char = '<'
        else:
            char = '>'
        print "%s (%s) %s %s (%s)" % (card1, pair[0], char, card2, pair[1])
    sets = ['AhKc', 'AcTcTc', '2c', 'Gc', '2f', '2h2']
    for item in sets:
        print "parsing %s" % item
        try:
            print "--> %r" % Card.many_from_text(item)
        except (ValueError, TypeError) as err:
            print "--> %r" % err
    card0 = 'Ah'
    print "%s --> %s --> %s" % (card0, Card.from_text(card0),
                                Card.from_text(card0).to_mnemonic())

if __name__ == '__main__':
    main()
