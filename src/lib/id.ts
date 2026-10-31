let counter = 0;

/** Generates a reasonably unique, sortable id without external deps. */
export function generateId(prefix: string): string {
  counter = (counter + 1) % 10000;
  return `${prefix}_${Date.now().toString(36)}${counter.toString(36)}${Math.random()
    .toString(36)
    .slice(2, 6)}`;
}
