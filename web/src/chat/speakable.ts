/** An answer as it is spoken in Voice Chat. The words change, never the content: every score, level and confidence,
 *  and every PLACEHOLDER or SAMPLE warning, is read out. Only the long list of reasons is shortened to the first
 *  few, with a pointer to the screen, where the full answer is shown in the conversation. */

/** Reasons ("- ..." lines) read aloud before pointing to the screen. */
export const SPOKEN_REASONS = 2;

const REPLACEMENTS: [RegExp, string][] = [
  [/(\d+(?:\.\d+)?)\/(\d+)/g, "$1 out of $2"],
  [/#(\d+)/g, "number $1"],
  [/(\d)\s*°C/g, "$1 degrees Celsius"],
  [/>=/g, " at least "],
  [/<=/g, " at most "],
  [/(\d+) h\b/g, "$1 hours"],
  [/\bx(\d+)\b/g, "times $1"],
  [/\be\.g\.\s*/g, "for example "],
  [/\s+[—–]\s+/g, ", "],
  [/[[\]]/g, ""],
];

/** One line in spoken form. */
export function speakLine(line: string): string {
  let text = line.trim().replace(/^[-•]\s*/, "").replace(/^(\d+)\.\s+/, "Number $1, ");
  for (const [pattern, replacement] of REPLACEMENTS) text = text.replace(pattern, replacement);
  text = text.replace(/\s{2,}/g, " ").trim();
  return text && !/[.!?:,]$/.test(text) ? `${text}.` : text;
}

export function speakable(answer: string): string {
  const spoken: string[] = [];
  let reasons = 0;
  let skipped = 0;
  let pointerAt = -1; // where the skipped reasons were: the lines after them (the warnings) still follow
  for (const line of answer.split("\n")) {
    if (!line.trim()) continue;
    if (/^\s*-\s/.test(line)) {
      reasons += 1;
      if (reasons > SPOKEN_REASONS) {
        skipped += 1;
        if (pointerAt < 0) pointerAt = spoken.length;
        continue;
      }
    }
    spoken.push(speakLine(line));
  }
  if (skipped) {
    spoken.splice(pointerAt, 0, `${skipped} more ${skipped === 1 ? "reason is" : "reasons are"} shown on screen.`);
  }
  return spoken.join(" ");
}

/** Text split into sentences of at most `limit` characters: some browsers stop a long utterance part-way. */
export function chunks(text: string, limit = 220): string[] {
  // A sentence ends at . ! or ? followed by a space: decimals (0.62) stay whole.
  const sentences = text.split(/(?<=[.!?])\s+/);
  const out: string[] = [];
  let current = "";
  for (const sentence of sentences.map((s) => s.trim()).filter(Boolean)) {
    if (current && (current + " " + sentence).length > limit) {
      out.push(current);
      current = sentence;
    } else {
      current = current ? `${current} ${sentence}` : sentence;
    }
  }
  if (current) out.push(current);
  return out;
}
