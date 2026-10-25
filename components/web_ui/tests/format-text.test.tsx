import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FormattedText } from "../src/features/chat/FormattedText";
import { parseBlocks, parseInline } from "../src/features/chat/format-text";

describe("parseInline", () => {
  it("splits bold from plain text and leaves unmatched markers alone", () => {
    expect(parseInline("report within **30 days** please")).toEqual([
      { kind: "text", text: "report within " },
      { kind: "bold", text: "30 days" },
      { kind: "text", text: " please" },
    ]);
    expect(parseInline("one ** marker only")).toEqual([
      { kind: "text", text: "one ** marker only" },
    ]);
    expect(parseInline("")).toEqual([]);
  });

  it("handles Thai and Japanese around the markers", () => {
    expect(parseInline("ภายใน **15 วัน** นับจาก")).toHaveLength(3);
    expect(parseInline("事故の日から**60日以内**にご連絡")).toHaveLength(3);
  });
});

describe("parseBlocks", () => {
  it("groups consecutive bullets into one list and keeps paragraphs apart", () => {
    const blocks = parseBlocks("Rules:\n- one\n- two\n\nDone.");
    expect(blocks.map((b) => b.kind)).toEqual([
      "paragraph",
      "list",
      "paragraph",
    ]);
    expect(blocks[1]).toMatchObject({
      items: [[{ text: "one" }], [{ text: "two" }]],
    });
  });

  it("treats numbered lines as list items and ignores blank lines", () => {
    expect(parseBlocks("1. first\n2. second").map((b) => b.kind)).toEqual([
      "list",
    ]);
    expect(parseBlocks("\n\n")).toEqual([]);
  });
});

describe("FormattedText", () => {
  it("shows bold text as bold with no asterisks", () => {
    render(<FormattedText lang="en" text="You have **30 days** to report." />);
    expect(screen.getByText("30 days").tagName).toBe("STRONG");
    expect(document.body).not.toHaveTextContent("**");
  });

  it("renders bullet lists and carries the language", () => {
    const { container } = render(
      <FormattedText lang="th" text={"- ข้อแรก\n- ข้อสอง"} />,
    );
    expect(container.querySelectorAll("li")).toHaveLength(2);
    expect(container.firstElementChild).toHaveAttribute("lang", "th");
  });

  it("never turns text into markup", () => {
    const { container } = render(
      <FormattedText
        lang="en"
        text={'<img src=x onerror="alert(1)"> **<b>hi</b>**'}
      />,
    );
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("b")).toBeNull();
    expect(container).toHaveTextContent('<img src=x onerror="alert(1)">');
  });
});
