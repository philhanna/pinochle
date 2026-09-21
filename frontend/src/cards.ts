// Card codes, and the order a hand is laid out in.
//
// A card on the wire is two characters: rank letter then suit letter, so the
// ten of spades is "TS" (the wire format is fixed-width, which is why ten is
// "T" and not "10"). Two copies of every card exist in a 48-card pinochle
// deck, so a code is not unique within a hand and a card can only ever be
// removed one copy at a time.

/** A suit as the wire names it. */
export type SuitName = "SPADES" | "HEARTS" | "DIAMONDS" | "CLUBS";

/** A two-character card code, e.g. `"TS"`. */
export type CardCode = string;

const SUIT_LETTERS: Record<SuitName, string> = {
  SPADES: "S",
  HEARTS: "H",
  DIAMONDS: "D",
  CLUBS: "C",
};

// FR-23: spades, hearts, clubs, diamonds — black, red, black, red. The
// colours alternate so that every group is bounded by the other colour and
// the seam between two suits is visible at a glance; hearts beside diamonds
// in a fanned hand, where only the corner index of each card shows, is the
// one adjacency that has to be read rather than seen.
const SUIT_ORDER = ["S", "H", "C", "D"] as const;

// Which of those are red, for the alternation above.
const RED_SUITS = new Set(["H", "D"]);

// FR-23: descending by rank within a suit. Note the pinochle order — the ten
// sits above the king (FR-18) — so this is not the familiar sequence.
const RANK_ORDER = ["A", "T", "K", "Q", "J", "9"] as const;

/**
 * Return `cards` in the order a hand is displayed (FR-23, FR-23a).
 *
 * Grouped by suit and descending by rank within each suit. Once trump is
 * named it moves to the leftmost group, the other three keeping their
 * relative order — the one re-sort a hand undergoes during a round.
 *
 * Sorts a copy: the reducer's state is never mutated in place.
 */
export function sortHand(cards: CardCode[], trump: SuitName | null = null): CardCode[] {
  const suits = suitOrder(trump);
  return [...cards].sort((a, b) => {
    const bySuit = rank(suits, suitLetterOf(a)) - rank(suits, suitLetterOf(b));
    return bySuit !== 0
      ? bySuit
      : rank(RANK_ORDER, rankLetterOf(a)) - rank(RANK_ORDER, rankLetterOf(b));
  });
}

/** The suit letters in display order, trump first if it is known (FR-23a). */
function suitOrder(trump: SuitName | null): readonly string[] {
  return trump === null ? SUIT_ORDER : alternatingFrom(SUIT_LETTERS[trump]);
}

/**
 * The four suits beginning at `first`, still alternating in colour (FR-23a).
 *
 * Moving trump to the left cannot leave the other three where they were: a
 * red trump in front of spades, hearts, clubs, diamonds would strand the
 * other red suit against it. So the rest follow in alternating colour, and
 * where either suit of the wanted colour would do, the one earlier in FR-23's
 * order goes first — which keeps as much of that order as alternating allows.
 *
 * The deck has two suits of each colour, so the suit this needs at each step
 * always exists.
 */
function alternatingFrom(first: string): string[] {
  const byColour = {
    red: SUIT_ORDER.filter((s) => isRed(s) && s !== first) as string[],
    black: SUIT_ORDER.filter((s) => !isRed(s) && s !== first) as string[],
  };
  const order = [first];
  let wantRed = !isRed(first);
  // The other three suits, each the opposite colour to the one before it.
  for (let i = 0; i < 3; i += 1) {
    order.push(...(wantRed ? byColour.red : byColour.black).splice(0, 1));
    wantRed = !wantRed;
  }
  return order;
}

/** Whether a suit letter names a red suit. */
function isRed(letter: string): boolean {
  return RED_SUITS.has(letter);
}

/** Position of `value` in `order`, or the end if it is not there at all. */
function rank(order: readonly string[], value: string): number {
  const index = order.indexOf(value);
  return index === -1 ? order.length : index;
}

/** The suit letter of a card code. */
export function suitLetterOf(card: CardCode): string {
  return card.slice(1, 2);
}

/** The rank letter of a card code. */
export function rankLetterOf(card: CardCode): string {
  return card.slice(0, 1);
}

/** Whether `card` belongs to `suit`. */
export function isSuit(card: CardCode, suit: SuitName): boolean {
  return suitLetterOf(card) === SUIT_LETTERS[suit];
}

/**
 * Return `cards` with one copy of `card` removed.
 *
 * One copy, not every match: a hand can hold both copies of a card, and
 * playing one leaves the other.
 */
export function removeOne(cards: CardCode[], card: CardCode): CardCode[] {
  const index = cards.indexOf(card);
  return index === -1 ? [...cards] : [...cards.slice(0, index), ...cards.slice(index + 1)];
}

/** The URL of a card's face image, as the cards router serves it (UI-16). */
export function faceUrl(card: CardCode): string {
  return `/cards/faces/${encodeURIComponent(card)}`;
}

/** The URL of the card-back image (UI-5). */
export function backUrl(name = "blue"): string {
  return `/cards/backs/${encodeURIComponent(name)}`;
}
