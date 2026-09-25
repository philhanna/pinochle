// The trick being taken in (UI-15).
//
// When the server clears a completed trick, the four cards are gathered into a
// pile, turned face down and carried to the winning team's stack. Purely
// cosmetic: the clones fly over the table while the state still holds the
// trick, and the caller applies `trick_cleared` when they land.

import { backUrl } from "./cards.js";

const GATHER_END = 0.3;
const FLIP_END = 0.55;
const FLIGHT_MS = 1000;

/** How a card sits in the trick before it is gathered (see `.trick .played`). */
const TILT: Record<string, number> = { left: -6, right: 6 };

/**
 * Fly the cards now in the trick to `target`, then call `done`.
 *
 * Returns false, having done nothing, when there is nothing to fly or the
 * player has asked for reduced motion; the caller then just applies the frame.
 */
export function sweepTrick(target: DOMRect, done: () => void): boolean {
  const played = Array.from(document.querySelectorAll<HTMLImageElement>(".trick .played"));
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (played.length === 0 || reduced || typeof played[0]?.animate !== "function") {
    return false;
  }

  const scale = stageScale();
  const boxes = played.map((image) => image.getBoundingClientRect());
  const centres = boxes.map((box) => [box.x + box.width / 2, box.y + box.height / 2] as const);
  const gather = [
    centres.reduce((sum, c) => sum + c[0], 0) / centres.length,
    centres.reduce((sum, c) => sum + c[1], 0) / centres.length,
  ] as const;
  const goal = [target.x + target.width / 2, target.y + target.height / 2] as const;

  const overlay = document.createElement("div");
  overlay.className = "sweep";
  const animations: Animation[] = [];

  played.forEach((image, index) => {
    const width = image.offsetWidth * scale;
    const height = image.offsetHeight * scale;
    const [cx, cy] = centres[index] as readonly [number, number];
    const tilt = TILT[image.classList[2] ?? ""] ?? 0;
    const settle = (index - (played.length - 1) / 2) * 3;

    const card = document.createElement("div");
    card.className = "sweep-card";
    card.style.cssText =
      `left:${cx - width / 2}px;top:${cy - height / 2}px;width:${width}px;height:${height}px`;
    const inner = document.createElement("div");
    inner.className = "sweep-inner";
    const face = document.createElement("img");
    face.className = "card sweep-face";
    face.src = image.src;
    face.alt = "";
    const back = document.createElement("img");
    back.className = "card sweep-back";
    back.src = backUrl();
    back.alt = "";
    inner.append(face, back);
    card.append(inner);
    overlay.append(card);

    const shrink = Math.min(1, (target.width - 18 * scale) / width);
    const move = (x: number, y: number, turn: number, size: number) =>
      `translate(${x}px, ${y}px) rotate(${turn}deg) scale(${size})`;
    const gathered = move(gather[0] - cx + settle, gather[1] - cy + settle, settle, 1);
    animations.push(card.animate([
      { transform: move(0, 0, tilt, 1), offset: 0 },
      { transform: gathered, offset: GATHER_END },
      { transform: gathered, offset: FLIP_END },
      { transform: move(goal[0] - cx, goal[1] - cy, 0, shrink), offset: 1 },
    ], { duration: FLIGHT_MS, easing: "ease-in-out", fill: "forwards" }));
    animations.push(inner.animate([
      { transform: "perspective(900px) rotateY(0deg)", offset: 0 },
      { transform: "perspective(900px) rotateY(0deg)", offset: GATHER_END },
      { transform: "perspective(900px) rotateY(180deg)", offset: FLIP_END },
      { transform: "perspective(900px) rotateY(180deg)", offset: 1 },
    ], { duration: FLIGHT_MS, easing: "ease-in-out", fill: "forwards" }));
  });

  document.body.append(overlay);
  document.body.classList.add("sweeping");

  const finish = () => {
    overlay.remove();
    document.body.classList.remove("sweeping");
    done();
  };
  Promise.all(animations.map((a) => a.finished)).then(finish, finish);
  return true;
}

/** The factor the stage is scaled by to fit the window (UI-17). */
function stageScale(): number {
  const stage = document.getElementById("stage");
  const value = stage === null ? NaN : parseFloat(stage.style.getPropertyValue("--stage-scale"));
  return Number.isFinite(value) && value > 0 ? value : 1;
}
