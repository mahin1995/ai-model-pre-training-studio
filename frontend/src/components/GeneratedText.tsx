export function GeneratedText({ text, className }: { text: string; className?: string }) {
  const whitespaceOnly = text.length > 0 && text.trim().length === 0;
  return <>
    <pre className={className}>{text.length === 0 ? "[Empty continuation]" : whitespaceOnly ? "[Whitespace-only continuation]" : text}</pre>
    {whitespaceOnly && <p className="dataset-caption">The model generated whitespace without visible text. Inspect the escaped text to see line breaks, spaces or tabs.</p>}
    <details><summary>Escaped generated text</summary><pre className="inference-ids">{JSON.stringify(text)}</pre></details>
  </>;
}
