export type Inline =
  { kind: "text"; text: string } | { kind: "bold"; text: string };
export type Block =
  { kind: "paragraph"; inline: Inline[] } | { kind: "list"; items: Inline[][] };

const BULLET = /^\s*(?:[-*•]|\d+\.)\s+(.*)$/;
const BOLD = /\*\*([^*\n]+)\*\*/g;

export function parseInline(line: string): Inline[] {
  const parts: Inline[] = [];
  let last = 0;
  for (const match of line.matchAll(BOLD)) {
    if (match.index > last)
      parts.push({ kind: "text", text: line.slice(last, match.index) });
    parts.push({ kind: "bold", text: match[1]! });
    last = match.index + match[0].length;
  }
  if (last < line.length) parts.push({ kind: "text", text: line.slice(last) });
  return parts;
}

export function parseBlocks(text: string): Block[] {
  const blocks: Block[] = [];
  for (const raw of text.split("\n")) {
    const bullet = BULLET.exec(raw);
    if (bullet) {
      const item = parseInline(bullet[1]!);
      const previous = blocks[blocks.length - 1];
      if (previous?.kind === "list") previous.items.push(item);
      else blocks.push({ kind: "list", items: [item] });
    } else if (raw.trim() !== "") {
      blocks.push({ kind: "paragraph", inline: parseInline(raw) });
    }
  }
  return blocks;
}
