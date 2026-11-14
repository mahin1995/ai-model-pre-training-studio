import { useRef, useState } from "react";
import { encodeText } from "../services/tokenizers";
import type { EncodingPreview } from "../types/tokenizers";

export function TokenizerPlayground({ projectId, runId }: { projectId: string; runId: string }) {
  const [text, setText] = useState("আমি বাংলা ভাষা শিখছি। Hello, world! 👋 [EOS]");
  const [result, setResult] = useState<EncodingPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const sequence = useRef(0);
  const bytes = new TextEncoder().encode(text).length;
  async function inspect(page = 1) {
    const current = ++sequence.current;
    setBusy(true); setError("");
    try { const next = await encodeText(projectId, runId, text, page); if (current === sequence.current) setResult(next); }
    catch (e) { if (current === sequence.current) setError(e instanceof Error ? e.message : "Encoding failed."); }
    finally { if (current === sequence.current) setBusy(false); }
  }
  return <section className="tokenizer-playground"><div className="form-heading"><span className="eyebrow">ENCODE / DECODE</span><h3>See how your text becomes tokens.</h3><p>Byte-level pieces may look unusual. The full decoded text should match your input exactly.</p></div>
    {error && <div className="error-banner" role="alert">{error}</div>}
    <label htmlFor="tokenizer-input">Text to tokenize</label>
    <textarea id="tokenizer-input" dir="auto" value={text} rows={4} onChange={(e) => { ++sequence.current; setText(e.target.value); setResult(null); setBusy(false); }} />
    <div className="review-tools"><button className="primary" disabled={busy || bytes > 16384} onClick={() => void inspect()}>{busy ? "Encoding…" : "Encode text"}</button><span>{bytes.toLocaleString()} / 16,384 UTF-8 bytes</span></div>
    {result && <><div className="dataset-stats"><div><strong>{result.tokenCount.toLocaleString()}</strong><span>Tokens</span></div><div><strong>{result.bytesPerToken.toFixed(2)}</strong><span>UTF-8 bytes / token</span></div><div><strong>{result.roundTripMatches ? "Exact match" : "Mismatch"}</strong><span>Full text round-trip</span></div></div>
      <label>Decoded text</label><pre className="tokenizer-decoded" dir="auto">{result.decodedText || "(empty text)"}</pre>
      <div className="token-table-scroll"><table className="token-table"><thead><tr><th>Index</th><th>Token ID</th><th>Byte-level piece</th><th>Character offsets</th></tr></thead><tbody>{result.tokens.map((token) => <tr key={token.index}><td>{token.index}</td><td>{token.id}</td><td><code>{token.piece}</code></td><td>{token.offset.join(" – ")}</td></tr>)}</tbody></table></div>
      <div className="preview-pagination"><button className="secondary" disabled={busy || result.tokenPage <= 1} onClick={() => void inspect(result.tokenPage - 1)}>Previous tokens</button><span>Page {result.tokenPage} of {Math.max(1, Math.ceil(result.tokenCount / 256))}</span><button className="secondary" disabled={busy || result.tokenPage * 256 >= result.tokenCount} onClick={() => void inspect(result.tokenPage + 1)}>Next tokens</button></div>
    </>}
  </section>;
}
