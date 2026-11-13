import { describe, expect, it } from "vitest";
import { applySuggestion, cleanReviewText, reviewSuggestions } from "./text";

describe("reviewed page text", () => {
  it("suggests whole words without automatically changing text", () => {
    const original = "হললো: ককোননো? ভাললো। কররোটা";
    expect(reviewSuggestions(original).map((s) => s.before)).toEqual(["হললো", "ককোননো", "ভাললো"]);
    expect(applySuggestion(original, "হললো", "হলো")).toBe("হলো: ককোননো? ভাললো। কররোটা");
    expect(applySuggestion("কররোটা কররো", "কররো", "করো")).toBe("কররোটা করো");
  });
  it("preserves meaningful joiners, paragraphs and clause references during explicit cleanup", () => {
    expect(cleanReviewText("  বাংলা\u200c\u200d\u200b\r\n\r\n e\u0301  \nClause: 2.4.1.2.1")).toBe("বাংলা\u200c\u200d\n\né\nClause: 2.4.1.2.1");
  });
});
