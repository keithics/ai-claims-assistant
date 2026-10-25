import { parseBlocks, type Inline } from "./format-text";

function renderInline(parts: Inline[]) {
  return parts.map((part, index) =>
    part.kind === "bold" ? <strong key={index}>{part.text}</strong> : part.text,
  );
}

export function FormattedText({ text, lang }: { text: string; lang: string }) {
  return (
    <div lang={lang} className="text">
      {parseBlocks(text).map((block, index) =>
        block.kind === "list" ? (
          <ul key={index}>
            {block.items.map((item, i) => (
              <li key={i}>{renderInline(item)}</li>
            ))}
          </ul>
        ) : (
          <p key={index}>{renderInline(block.inline)}</p>
        ),
      )}
    </div>
  );
}
