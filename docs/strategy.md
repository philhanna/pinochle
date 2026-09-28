# Pinochle — Learned Strategy

**Status:** Proposal — high-level design, not yet implemented
**Last updated:** 2026-09-27
**Replaces (when adopted):** the rules in `design.md` §7.4 for bidding, trump,
passing and play

---

## 1. Purpose and scope

`ComputerPlayerStrategy` makes its four real decisions by hand-written rule:

| Method | Current rule | Requirement |
| --- | --- | --- |
| `choose_bid` | 180 + best suit's meld and trick estimate, one increment at a time; yield to partner | FR-75a, FR-75d |
| `choose_trump` | the longest suit | FR-75e |
| `choose_cards_to_pass` | all trump, then aces, then low cards; protect own meld | FR-75b |
| `choose_play` | the highest legal card if partner is winning or leading, else the lowest | FR-75e |

These rules are placeholders: `_PARTNER_CONTRIBUTION` is commented as "to be
tuned by playing games", and "high to partner, low to opponent" knows nothing
of counters, cutting with trump, or whether a higher card could win the trick.

This document describes a training system, modelled on AlphaZero, that learns
all four decisions by self-play. The system produces a trained network, a
search procedure that uses it, and a new implementation of the four methods
that consults both.

It covers:

- why AlphaZero cannot be applied unchanged, and what changes (§2);
- the overall loop (§3);
- the round simulator that self-play runs on (§4);
- what a seat observes and how it is encoded (§5);
- the network (§6);
- search under hidden information (§7);
- the four decisions in detail (§8);
- self-play, training targets and the training loop (§9);
- evaluation and gating (§10);
- how the result plugs into the existing code (§11);
- a phased plan (§12);
- risks and open questions (§13).

Out of scope: dealer selection (`choose_draw_position` is correctly random),
and the two decisions FR-75e currently hard-codes (accepting a lone contract,
never tossing in). §8.5 notes that the value network makes both cheap to add
later.

---

## 2. From AlphaZero to Pinochle

AlphaZero combines a policy/value network with Monte Carlo tree search (MCTS).
Search improves on the network's policy, the network is trained to predict
search's output and the game's result, and the loop repeats. The idea
carries over; four assumptions do not.

| AlphaZero assumes | Pinochle has | Consequence |
| --- | --- | --- |
| Perfect information | Three hidden hands (FR-22, FR-74) | Search runs over *sampled deals* consistent with what the seat has seen (§7) |
| Two players, zero-sum | Four seats in two partnerships | Value is a *team* score differential; partners share it (§9.2) |
| Deterministic after the start | One chance event: the deal | The deal is sampled, never searched |
| One homogeneous action type | Bid, name trump, choose four cards, play a card | One shared trunk, one policy head per decision (§6) |

Two properties of the game make the adaptation tractable:

- **The deal is the only randomness.** Once the cards are dealt, every
  transition is a player's choice. Sampling the hidden hands therefore turns
  the remainder of the round into a perfect-information game.
- **Information leaks quickly.** Meld is exposed face up before the first
  trick (FR-44), every played card is public (FR-57), and the follow-suit and
  must-trump rules (FR-53) reveal voids. By mid-round the set of consistent
  deals is small, and sampling from it is accurate.

The unit of self-play is one **round**, not one game to 2000. A round has a
clean, bounded score (FR-59–FR-64), and round-level episodes are some twenty
times shorter than full games. §13 notes when game-level context would
matter.

---

## 3. Overview

```
╔══════════════════════════════════════════════════════════════════════════╗
║  SELF-PLAY WORKERS  (many, in parallel)                                  ║
║                                                                          ║
║   deal ──► for each decision of each seat:                               ║
║              encode the seat's information state (§5)                    ║
║              sample D deals consistent with it (§7.2)                    ║
║              run guided search in each; pool root visit counts (§7.3)    ║
║              record (state, visit distribution); act                     ║
║           ──► score the round; attach each seat's team outcome           ║
╚═══════════════════════════════╤══════════════════════════════════════════╝
                                │ (state, π, z) samples
                                ▼
╔══════════════════════════════════════════════════════════════════════════╗
║  REPLAY BUFFER  — last N generations of samples                          ║
╚═══════════════════════════════╤══════════════════════════════════════════╝
                                │ minibatches
                                ▼
╔══════════════════════════════════════════════════════════════════════════╗
║  TRAINER                                                                 ║
║   loss = policy CE(π) + value CE(z) + belief CE(hidden hands) + L2       ║
╚═══════════════════════════════╤══════════════════════════════════════════╝
                                │ candidate weights
                                ▼
╔══════════════════════════════════════════════════════════════════════════╗
║  ARENA  — duplicate deals vs the current best and vs the rule baseline   ║
║   promote the candidate if it wins by a significant margin (§10)         ║
╚═══════════════════════════════╤══════════════════════════════════════════╝
                                │ best weights
                                ▼
                     back to the self-play workers
```

**Data flow:** deal → per-decision search → (state, π) records → round score →
z attached → replay buffer → trainer → arena → best network → self-play.

---

## 4. The round simulator

Self-play and search need a fast, headless implementation of one round:
deal, bid, confirm, name trump, pass, meld, twelve tricks and score.

The authoritative rules already exist without any web or timing dependency.
`Round` (`pinochle/services/round.py`) drives the phase machine, and
`pinochle/domain/` supplies `detect_meld`, `Trick` and scoring. They are
unsuitable as the *search* engine for two reasons. Search clones a state
thousands of times per decision, and `copy.deepcopy` of a `Round` is slow.
Search must also construct a state from a *sampled* deal, which `Round`
deliberately cannot do, since it only deals from its own shuffle.

The design therefore has two engines:

- **`FastRound`**, a compact state for training: 24 card types × 2 copies as
  small integer arrays, with cheap copy, legal-move generation and scoring.
  It can be seeded with any deal.
- **`Round`** remains the reference. A differential test plays many thousands
  of random rounds through both engines with identical moves and asserts
  identical legal-move sets, trick winners, meld and scores. This keeps
  FR-73 true of the learned player: it learns the rules the server enforces,
  not an approximation of them.

The two copies of a card are interchangeable (FR-19), so states and actions
are expressed over the 24 card *types*, never over physical cards. This
halves the action space and removes duplicate branches from search.

---

## 5. Information state

### 5.1 What a seat may know

FR-74 limits a strategy to what its seat is entitled to see. The learned
strategy needs more of that public information than `SeatView` currently
carries:

| Information | In `SeatView` today | Needed for |
| --- | --- | --- |
| Own hand | yes | everything |
| Bid history, high bid, partner, bid winner | yes | bidding, belief |
| Trump | yes | pass, play |
| Exposed meld of every seat | yes | play, belief |
| Cards in the current trick, with who played them | cards only | play |
| **Completed tricks: who led, who played what, who won** | no | play, belief |
| **The four cards this seat passed or received** | no | play, belief |
| **Dealer, and seat order relative to it** | no | bidding |
| **Card points taken so far by each team** | no | play |
| Cumulative game scores | no | only game-level value (§13) |

Every bolded row is public or is the seat's own knowledge (FR-38 shows the
pass to both bidding-team members), so extending `SeatView` does not weaken
FR-74. `Round` already holds all of it, in `_tricks` and `_passed_cards`.

### 5.2 Encoding

Seats are encoded **relative to the observer**: self, left opponent, partner,
right opponent. This builds seat-rotation symmetry into the network.

The information state becomes a fixed-size vector:

- **Card planes**, each 24 × {0, 1, 2}: own hand; cards passed; cards
  received; each other seat's exposed meld cards not yet played; cards played
  by each seat; cards in the current trick, per seat.
- **Auction**: the bid sequence as (relative seat, amount-or-pass) tokens,
  the high bid, and the dealer's relative seat.
- **Contract**: bid winner's relative seat, contract amount, trump one-hot.
- **Play context**: trick number, relative seat on lead, card points and
  tricks taken per team, and whether a trump has been played in this trick.
- **Phase** one-hot: which of the four decisions is being asked.

**Symmetry augmentation.** Suit relabelling is *not* a full symmetry of
Pinochle, because the pinochle meld (FR-47) names Q♠ and J♦. Swapping hearts
with clubs is exact, however, and doubles the training data for free. Trump
is not canonicalised to a fixed suit, for the same reason.

---

## 6. Network

One network with a shared trunk, so that what is learned about hand strength
in play also informs bidding and passing:

```
                  information state (§5.2)
                            │
                ┌───────────▼───────────┐
                │  trunk: residual MLP  │   (a small transformer over card
                │  (~1–5 M parameters)  │    and bid tokens is the upgrade path)
                └───────────┬───────────┘
      ┌──────────┬──────────┼──────────┬──────────┬──────────┐
      ▼          ▼          ▼          ▼          ▼          ▼
   bid head  trump head  pass head  play head  value head  belief head
   (§8.1)    4 suits     24 types   24 types   score bins  24×2 → seat
```

- Each **policy head** outputs logits over its action space. Illegal actions
  are masked to −∞ before the softmax, so the network cannot propose an
  illegal move.
- The **value head** predicts the round's team score differential (§9.2) as
  a categorical distribution over bins, rather than as a single scalar.
  Round outcomes are heavy-tailed: going set on a big contract, or a doubled
  run worth 1500, would dominate a squared-error loss.
- The **belief head** predicts, for each hidden physical card, which of the
  other three seats holds it. It is trained on ground truth the simulator
  knows for free. It shapes the trunk toward reading the table, and it
  serves the deal sampler in stage 2 (§7.2).

The network is kept small deliberately. The input is a few hundred numbers,
the game is short, and inference must fit comfortably inside the one-second
move delay (FR-75c) on a CPU.

---

## 7. Search under hidden information

### 7.1 Approach

The recommended starting point is **guided perfect-information Monte Carlo
(PIMC)**, which works like this:

1. Sample D complete deals consistent with the seat's information state.
2. In each deal, run S iterations of AlphaZero's PUCT search, with priors
   and leaf values from the network.
3. Sum root visit counts across the D searches; that sum is the search
   policy π.

PIMC is simple, embarrassingly parallel, and strong in trick-taking games
such as Bridge and Skat. Its known flaw is *strategy fusion*: inside one
sampled deal the searcher acts as if it could see every hand. The mitigation
is that every non-root seat's prior comes from the network applied to *that
seat's own* information state in the sampled deal (§7.3), never to the full
deal, so the modelled opponents do not play clairvoyantly. If evaluation shows
fusion errors (§10.3), the upgrade is single-observer information-set MCTS,
which shares one tree across deals. It uses the same network and needs no
retraining.

### 7.2 Sampling consistent deals

A sampled deal must place every unseen card so that the seat's whole history
remains possible. The hard constraints are:

- the seat's own hand, and the cards it passed or received;
- each seat's exposed meld cards, minus those it has since played;
- each seat's remaining hand size;
- voids and ceilings inferred from FR-53. A seat that did not follow the
  led suit holds none of it. A seat that did not trump when void holds no
  trump. A seat that did not beat the highest trump when obliged holds no
  trump above it.

These constraints are sampled exactly by assigning card types to seats with a
backtracking or count-matrix sampler. Rejection sampling fails once the
constraints tighten late in a round.

Hard constraints ignore the soft information in the auction: a seat that bid
400 probably holds meld. The sampler therefore improves in two stages:

1. **Uniform over consistent deals.** This is correct but blind to bidding.
   It is used from the start.
2. **Weighted by behaviour.** Each sampled deal is weighted by the product of
   the network's probabilities that each other seat would have made the bids
   and plays it actually made, given that seat's hand in the sample.
   Alternatively, the belief head proposes deals directly. Either way, the
   network's model of how players act becomes its model of what they hold.

### 7.3 Search within one sampled deal

- Nodes are full states of the sampled deal. At each node the seat to move
  is encoded from *its own* perspective (§5), and the network supplies that
  seat's masked prior and value.
- The value is converted to the root seat's team perspective. The
  differential is zero-sum between teams (§9.2), so the value is negated
  exactly when the seat to move is on the other team.
- Selection uses PUCT, as in AlphaZero. Dirichlet noise is added to root
  priors during self-play only.
- Search depth is bounded by the round: at most about 70 decisions remain
  from the first bid. In practice the value head cuts search off long
  before the end.

---

## 8. The four decisions

### 8.1 `choose_bid`

- **Actions:** pass, or bid `high + 10·k` for k = 1 … K, where the opening
  bid is fixed at 250 (FR-27) and K is around 15. Jump bids become
  available, which the current strategy never makes. A cap on the contract
  (for example 1000) keeps the head finite. The cap is set well above any
  contract self-play has been observed to make, and is revisited if bids
  cluster near it.
- **Search:** the auction is searched like any other phase. Its leaf values
  are the value head's estimate of the round *given* the contract, the
  declarer and the bidder's hand, which is exactly the quantity the
  hand-tuned `_PARTNER_CONTRIBUTION` approximates. Bidding is the hardest
  decision to learn: its value depends on play, passing and trump choice
  that happen later, which is why §12 trains it last.
- **Emergent behaviour, not rules:** FR-75d's "stop bidding against your
  partner" and the run exception fall out of the value of each contract,
  rather than being coded. Partnership bidding conventions may also emerge
  (for example, a first bid that signals meld). These are legitimate, since
  bids are public, but they are learned against partners who share them;
  see §13.

### 8.2 `choose_trump`

- **Actions:** four suits, masked to none. Any suit is legal.
- **Search:** four root children. With so few choices, search can afford
  many deals per child. The pass and meld phases follow in the tree, so the
  choice accounts for what the partner is likely to send.
- The network learns what "longest suit" misses: a run or trump marriage in
  a shorter suit, and aces that will take tricks as off-suit leads.

### 8.3 `choose_cards_to_pass`

Choosing 4 of 12 cards (495 subsets, fewer with duplicates) or 4 of 16
(1,820) is too large for one flat head. The choice is therefore made as
**four sequential sub-actions**, each picking one card type from the pass
head:

- The mask allows only card types still held.
- To make the subset order-free, each pick must be at or above the previous
  pick's index in a fixed card order, and at the same index only while a
  second copy remains. Each subset then has exactly one path.
- Search treats the four picks as ordinary tree levels owned by the same
  seat.

The same head serves both directions of the exchange. A "passing back" flag
in the state distinguishes them (FR-40). The partner learns what the
declarer needs, and the declarer learns what to return. That includes cases
the current rule forbids, such as returning a trump to protect a partner's
meld, if that scores better.

### 8.4 `choose_play`

- **Actions:** 24 card types, masked to `Round.legal_plays` (FR-53).
- **Search:** this is where PIMC is strongest. After meld is exposed, much of
  each hand is known, and after a few tricks the sampler is nearly exact.
- The network learns what the fixed rule misses: "smearing" counters (A, 10,
  K, Q) rather than simply the highest card onto a partner's winning trick,
  playing high enough to take a trick an opponent is winning, saving trump to
  cut, and playing for the last-trick 10 (FR-60).

### 8.5 Free extensions

Two more decisions reduce to reading the value head, so no new head is
needed:

- **Lone contract** (FR-32): accept if the value of playing the contract is
  greater than 0, the value of abandoning the round.
- **Toss in** (FR-50b): compare the value of playing on with the known cost
  of tossing in (FR-50c).

Both remain hard-coded (FR-75e) until the requirements change.

---

## 9. Self-play and training

### 9.1 Episodes

All four seats play with the current best network and search. Each decision
records the acting seat's encoded state, the phase, the legal mask and the
search policy π. Early in the round, moves are sampled from π with a
temperature. Later moves are chosen greedily, so that the value targets
reflect strong play. Abandoned rounds (FR-31) are kept: passing out is a
real outcome, worth 0.

### 9.2 Value target

For each recorded state, z is the score differential from the acting seat's
team's point of view:

> z = (points applied to own team) − (points applied to the other team)

"Points applied" are the points FR-62–FR-64 add to or subtract from each
team: a set is negative, and a meld is voided when its team takes no trick.
The differential makes the round zero-sum between teams, which lets search
use a single value and negate it across teams (§7.3). Partners share z, so
cooperation is rewarded and nothing else is needed to make partners play as
a team.

### 9.3 Loss

| Term | Target | Weight |
| --- | --- | --- |
| Policy | π, cross-entropy, on the head for the recorded phase | 1 |
| Value | z, cross-entropy over score bins | 1 |
| Belief | true location of every hidden card | 0.1–0.5 |
| L2 | — | small |

### 9.4 Loop

A generation runs in four steps:

1. Self-play workers generate rounds with the current best network.
2. The trainer samples from a replay buffer of recent generations.
3. The candidate faces the arena (§10).
4. If promoted, the candidate becomes the network the workers use.

Workers batch network calls across many simultaneous games, since a single
position is too small to use the hardware well.

Search budgets (D deals × S simulations) start small and grow as the network
improves. A technique from KataGo, *playout cap randomisation*, is useful
here: most moves use a cheap search to make play diverse, and a random
fraction use a full search to make good policy targets.

---

## 10. Evaluation and gating

### 10.1 Duplicate deals

Card games are dominated by the luck of the deal, so naïve head-to-head
matches need enormous samples. The arena instead plays **duplicate**:

1. Each deal is played twice, with the two teams swapping seats.
2. Only the difference between the two results is scored.

Deal luck cancels out, and the variance of the comparison falls by an order
of magnitude.

### 10.2 Gating

A candidate replaces the best network only if its mean duplicate margin is
significantly positive (for example, a one-sided test at p < 0.05 over a few
thousand deal pairs).

### 10.3 Benchmarks

Every promoted network is also measured, with duplicate deals, against:

- the **rule-based `ComputerPlayerStrategy`**, the fixed yardstick that shows
  absolute progress;
- a **network-only** version of itself (no search), which measures what
  search adds and whether the network alone is good enough for zero-delay
  play;
- a **PIMC-only oracle check** on late-round positions, where exhaustive
  search over all consistent deals is feasible. It exposes strategy-fusion
  errors (§7.1).

Diagnostics reported alongside the score:

- contracts made and set, by contract size;
- average margin over contract;
- bid-to-outcome calibration;
- how often a seat bids against its partner;
- games won to 2000 in full-game matches.

---

## 11. Integration with the codebase

### 11.1 The strategy interface

Today the driver calls the four methods with narrow arguments. For example,
`choose_play(view.legal_plays)` (`pinochle/services/computer_driver.py`)
gives the strategy no way to see the trick, let alone the history. The
learned strategy needs the whole seat view. The change is:

- Extend `SeatView` with the rows in §5.1 and have `_build_seat_view` fill
  them from `Round`.
- Introduce a `PlayerStrategy` abstract base class (`abc.ABC`,
  `@abstractmethod`) in its own module. It declares
  `choose_draw_position`, `choose_bid`, `choose_trump`,
  `choose_cards_to_pass` and `choose_play`, each of the last four taking a
  `SeatView`.
- Adapt `ComputerPlayerStrategy` to that interface. It stays as the shipped
  default and as the training baseline.
- Add `LearnedPlayerStrategy` under `pinochle/strategies/`. It loads weights,
  encodes the `SeatView`, optionally searches, and returns an action. The
  composition root selects between the two strategies. FR-75 anticipates
  exactly this swap.

Training code — the fast simulator, self-play, the trainer and the arena —
lives outside the `pinochle/` package (for example under `training/`), just
as browser code lives under `frontend/`. Only the encoder, the network
forward pass and the search needed at play time ship in `pinochle/`, and the
encoder is shared by both so the two can never disagree.

### 11.2 Requirements the learned strategy must keep

- **FR-73, legality.** Masking guarantees a legal choice from the network.
  As a final guard, if the chosen card is somehow not in
  `view.legal_plays`, the strategy falls back to the rule-based choice and
  logs the fact.
- **FR-74, information.** The strategy's only input is the `SeatView`, and
  the deal sampler draws hidden hands from constraints and beliefs, never
  from the real `Round`.
- **FR-75c, latency.** The search budget at play time is set by time, not by
  a fixed simulation count, and kept well under the configured move delay.
  At delay 0 the strategy runs network-only.
- **NFR-7, reproducibility.** All sampling uses the strategy's injected
  `Random`, and inference is deterministic, so a seeded game remains
  reproducible.

### 11.3 Dependencies

Training needs a deep-learning framework (PyTorch). Serving needs only a
forward pass through a small network, which NumPy can do. Weights are
exported to a NumPy archive, so the served image gains NumPy and a weights
file, not PyTorch; see §13 for how this interacts with NFR-2.

---

## 12. Phased plan

Each decision's value depends on how well the later decisions are made, so
learning proceeds from the end of the round backwards. Each phase freezes
earlier decisions at the rule-based baseline:

| Phase | Learned | Fixed (rule-based) | Exit criterion |
| --- | --- | --- | --- |
| 0 | — | all | `FastRound` passes the differential test against `Round`; `SeatView` extended; arena reproduces baseline-vs-baseline ≈ 0 |
| 1 | play | bid, trump, pass | significant duplicate margin over baseline play |
| 2 | pass | bid, trump | margin over phase 1 |
| 3 | trump | bid | margin over phase 2 |
| 4 | bid | — | margin over phase 3; contracts made/set in a sensible ratio |
| 5 | all, jointly | — | continued self-play; sampler upgraded to behaviour weighting (§7.2) |
| 6 | — | — | `LearnedPlayerStrategy` wired in behind configuration; human playtesting |

Phase 1 is the best single place to start. Play is where the current
strategy is weakest, where search under hidden information is most
effective, and where every later phase's value estimates come from.

An optional warm start is to pre-train the policy heads to imitate the
rule-based strategy for a few epochs. The first self-play generation then
opens with sensible bids instead of random ones. AlphaZero itself starts
from nothing; here the warm start saves early generations of 250-bid-and-set
rounds, and self-play overwrites it quickly.

---

## 13. Risks and open questions

- **Strategy fusion.** PIMC may misplay positions where the right move
  depends on not knowing a card (for example, which way to finesse). The
  oracle check in §10.3 measures it, and single-observer information-set
  MCTS is the remedy (§7.1).
- **Self-play conventions.** Partners trained together may develop signals
  in bids and plays that only a copy of themselves understands. Such signals
  are legitimate, since the information is public, but a human partner will
  not read them. The rule-based benchmark and human playtesting show whether
  the network is strong in general or only strong with itself. Mixing a
  fraction of rounds against frozen older networks and the rule baseline
  keeps self-play from narrowing.
- **Round-level versus game-level value.** Maximising the expected round
  differential is nearly right for a race to 2000, but not at the end of a
  game. When a team needs only 60 more points, safe contracts are worth more
  than their expected score says. A game-level value head, conditioned on
  both cumulative scores and trained on full-game outcomes, can be added
  once the round-level system works. It requires cumulative scores in
  `SeatView`.
- **Bidding credit assignment.** Only four seats bid, most bids are passes,
  and the result arrives some 60 decisions later. Bidding may need larger
  search budgets or more self-play than the other phases, and should be
  judged on its calibration as well as its margin.
- **Dependency placement (open).** NFR-2 and the project's convention list
  every dependency in `[project.dependencies]`. Listing PyTorch there would
  put it into the single container image (NFR-11). Options: accept the
  larger image; split training into its own project with its own
  `pyproject.toml`; or amend NFR-2 for training-only tools. This needs a
  decision before phase 0 ends.
- **Requirements (open).** FR-75a, FR-75b, FR-75d and FR-75e describe the
  current rules as requirements. Shipping a learned strategy as the default
  means restating them as requirements on *any* strategy (legal, seat-view
  only, bounded latency), with the specific rules demoted to a description of
  the baseline. The same applies to FR-75's "ships exactly one strategy".
