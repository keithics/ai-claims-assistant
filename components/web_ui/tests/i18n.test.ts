import { describe, expect, it } from "vitest";
import { LANGUAGES, MESSAGES } from "../src/i18n/locales";
import { translate } from "../src/i18n/translate";

const english = MESSAGES.en;
const placeholders = (text: string) =>
  [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();

describe("locale files", () => {
  it("cover the six languages", () => {
    expect([...LANGUAGES].sort()).toEqual([
      "ceb",
      "en",
      "fil",
      "id",
      "ja",
      "th",
    ]);
  });

  it.each(LANGUAGES)("%s has exactly the same keys as English", (language) => {
    expect(Object.keys(MESSAGES[language]).sort()).toEqual(
      Object.keys(english).sort(),
    );
  });

  it.each(LANGUAGES)(
    "%s has no empty strings and keeps every placeholder",
    (language) => {
      for (const [key, value] of Object.entries(MESSAGES[language])) {
        expect(value.trim(), `${language}.${key}`).not.toBe("");
        expect(placeholders(value), `${language}.${key}`).toEqual(
          placeholders(english[key as keyof typeof english]),
        );
      }
    },
  );

  it("are written in each language's own script", () => {
    expect(MESSAGES.th["chat.send"]).toMatch(/[฀-๿]/);
    expect(MESSAGES.ja["chat.send"]).toMatch(/[぀-ヿ一-鿿]/);
  });
});

describe("translate", () => {
  it("fills placeholders", () => {
    expect(translate("en", "approval.filed", { id: "PH-5001" })).toBe(
      "Claim PH-5001 was filed.",
    );
    expect(translate("ja", "chat.pendingBanner", { count: 2 })).toContain("2");
  });

  it("leaves unknown placeholders visible instead of breaking", () => {
    expect(translate("en", "approval.filed")).toBe("Claim {id} was filed.");
  });
});
