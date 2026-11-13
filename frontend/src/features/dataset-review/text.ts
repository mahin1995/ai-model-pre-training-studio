const words: Record<string, string> = {
  "হললো": "হলো", "ককোননো": "কোনো", "কররো": "করো", "ভাললো": "ভালো", "গুললো": "গুলো", "বুঝঝো": "বুঝো", "ততো": "তো",
};
const pattern = (word: string) => new RegExp(`(?<![\\p{L}\\p{M}\\p{N}_])${word}(?![\\p{L}\\p{M}\\p{N}_])`, "gu");
export const reviewSuggestions = (text: string) => Object.entries(words)
  .map(([before, after]) => ({ before, after, count: [...text.matchAll(pattern(before))].length }))
  .filter((suggestion) => suggestion.count > 0);
export const applySuggestion = (text: string, before: string, after: string) => text.replace(pattern(before), after);
export const cleanReviewText = (text: string) => text.normalize("NFC").replace(/\r\n?/g, "\n")
  .replace(/[\u200b\ufeff]/g, "").split("\n").map((line) => line.replace(/[ \t]+/g, " ").trim()).join("\n").trim();
