from twisted.spread import pb
import random

class Rank(pb.Copyable, pb.RemoteCopy):
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
        return cmp(ranks_low_to_high.index(self), ranks_low_to_high.index(other))
    def __hash__(self):
        return hash(self.singular)
    @classmethod
    def from_mnemonic(cls, char):
        return rank_map[char]
pb.setUnjellyableForClass(Rank, Rank)

class Suit(pb.Copyable, pb.RemoteCopy):
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
        return cmp(suits_low_to_high.index(self), suits_low_to_high.index(other))
    def __hash__(self):
        return hash(self.text)
    @classmethod
    def from_mnemonic(cls, char):
        return suit_map[char]
pb.setUnjellyableForClass(Suit, Suit)

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

ranks_high_to_low = [ACE, KING, QUEEN, JACK, TEN, NINE, EIGHT, SEVEN, SIX, FIVE, FOUR, TREY, DEUCE]
ranks_low_to_high = list(reversed(ranks_high_to_low))

suits_high_to_low = [SPADES, HEARTS, DIAMONDS, CLUBS]
suits_low_to_high = list(reversed(suits_high_to_low))

rank_map = {
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

rank_invert = {v:k for k, v in rank_map.items()}

suit_map = {
    "s": SPADES,
    "h": HEARTS,
    "d": DIAMONDS,
    "c": CLUBS
    }

suit_invert = {v:k for k, v in suit_map.items()}

def Deck():
    return [Card(rank, suit) for rank in ranks_high_to_low for suit in suits_high_to_low]

rank_for_mask = {
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

suit_for_mask = {
    SPADES: 3,
    HEARTS: 2,
    DIAMONDS: 1,
    CLUBS: 0
    }

class Card(pb.Copyable, pb.RemoteCopy):
    def __init__(self, rank, suit):
        if not isinstance(rank, Rank):
            raise TypeError("rank is not a Rank")
        if not isinstance(suit, Suit):
            raise TypeError("suit is not a Suit")
        self.rank = rank
        self.suit = suit

    @classmethod
    def fromText(cls, text):
        """
        null-coalescing
        """
        if not text:
            return None
        if len(text) != 2:
            raise ValueError("Invalid card mnemonic: '%s'" % text)
        r, s = text
        if r not in rank_map:
            raise ValueError("Invalid rank mnemonic: '%s'" % r)
        if s not in suit_map:
            raise ValueError("Invalid suit mnemonic: '%s'" % s)
        return cls(rank_map[r], suit_map[s])

    @classmethod
    def manyFromText(cls, text):
        """
        null-coalescing
        """
        if not text:
            return None
        if len(text) % 2 != 0:
            raise ValueError("Invalid card list: '%s'" % text)
        return [cls.fromText(text[i*2:i*2+2]) for i in range(len(text) / 2)]

    def toMnemonic(self):
        """
        Return a two-character representation of a card, e.g. "7c" for the Seven of Clubs.
        Note that HandRange relies on this format, so the return value of this method should not
        be changed without considering the impact on HandRange.
        """
        return rank_invert[self.rank] + suit_invert[self.suit]
    
    def toMask(self):
        return 1 << (13 * suit_for_mask[self.suit] + rank_for_mask[self.rank])

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
    
    """
    Suits and Ranks are singletons, so we temporarily create clones, then use them to assign the
    appropriate singletons to self.suit and self.rank. This probably isn't the most pythonic way to
    do this, but it's certainly the shortest.
    """
    def postUnjelly(self):
        self.rank, = [rank for rank in ranks_high_to_low if rank.singular == self.rank.singular]
        self.suit, = [suit for suit in suits_high_to_low if suit.text == self.suit.text]
pb.setUnjellyableForClass(Card, Card)

def deal_card(excluded):
    """
    Warning! Dealt cards will be appended to excluded list!
    """
    deck = [Card(rank, suit) for rank in ranks_high_to_low for suit in suits_high_to_low]
    for ex in excluded:
        deck.remove(ex)
    card = random.choice(deck)
    excluded.append(card)
    return card

def deal_cards(excluded, number):
    return [deal_card(excluded) for _ in range(number)]

if __name__ == '__main__':
    pairs = [
        ('Ah', 'Ac'),
        ('Ac', 'Ah'),
        ('Ah', 'Ah'),
        ('Ah', 'Ks'),
        ('Ah', 'Kh'),
        ('Ah', 'Kc')
        ]
    for pair in pairs:
        card1 = Card.fromText(pair[0])
        card2 = Card.fromText(pair[1])
        result = cmp(card1, card2)
        if not result:
            ch = '='
        elif result < 0:
            ch = '<'
        else:
            ch = '>'
        print "%s (%s) %s %s (%s)" % (card1, pair[0], ch, card2, pair[1])
    sets = ['AhKc', 'AcTcTc', '2c', 'Gc', '2f', '2h2']
    for s in sets:
        print "parsing %s" % s
        try:
            print "--> %r" % Card.manyFromText(s)
        except (ValueError, TypeError) as e:
            print "--> %r" % e
    card0 = 'Ah'
    print "%s --> %s --> %s" % (card0, Card.fromText(card0),
                                Card.fromText(card0).toMnemonic())