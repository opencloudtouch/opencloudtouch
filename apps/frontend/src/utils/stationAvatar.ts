// All colours give >= 4.5:1 contrast with the white initials (WCAG AA).
const AVATAR_COLORS = [
  "#6264A7",
  "#C2303D",
  "#0069BC",
  "#00796B",
  "#8764B8",
  "#B8460E",
  "#038387",
  "#8E562E",
  "#3B5BDB",
  "#D13438",
  "#107C10",
  "#AC008C",
];

/**
 * Get initials for station avatar (Teams-style fallback when no favicon).
 * Two letters from first two words, or first two letters of single word.
 */
export function getStationInitials(name: string): string {
  const words = name.trim().split(/\s+/);
  const first = words[0];
  const second = words[1];
  if (words.length >= 2 && first && second) {
    return ((first[0] ?? "") + (second[0] ?? "")).toUpperCase();
  }
  return name.trim().substring(0, Math.min(2, name.trim().length)).toUpperCase();
}

/**
 * Generate a deterministic color from station name for avatar background.
 */
export function getAvatarColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = (name.codePointAt(i) ?? 0) + ((hash << 5) - hash);
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length] ?? "#6264A7";
}
