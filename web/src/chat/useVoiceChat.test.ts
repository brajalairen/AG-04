import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { chunks, speakable } from "./speakable";
import { useChatStore, type ChatMessage } from "./useChatStore";
import {
  BLOCKED, isEcho, liveRecognisers, PAUSED, UNSUPPORTED, useVoiceChat,
} from "./useVoiceChat";

/** SpeechRecognition as Chrome behaves: results accumulate within a session; stop() delivers what is pending and
 *  then ends; abort() ends at once (onend still fires if a handler is attached). */
class FakeRecognition {
  static instances: FakeRecognition[] = [];
  lang = "";
  continuous = false;
  interimResults = false;
  started = false;
  ended = false;
  results: (Array<{ transcript: string }> & { isFinal: boolean })[] = [];
  onresult: ((event: unknown) => void) | null = null;
  onerror: ((event: { error: string }) => void) | null = null;
  onend: (() => void) | null = null;
  constructor() {
    FakeRecognition.instances.push(this);
  }
  start() {
    this.started = true;
  }
  stop() {
    this.end();
  }
  abort() {
    this.end();
  }
  end() {
    if (this.ended) return;
    this.ended = true;
    this.onend?.();
  }
  /** Words heard: an interim result, or a final one. Interim text replaces the previous interim result. */
  say(text: string, final = false) {
    const last = this.results[this.results.length - 1];
    const result = Object.assign([{ transcript: text }], { isFinal: final });
    if (last && !last.isFinal) this.results[this.results.length - 1] = result;
    else this.results.push(result);
    this.onresult?.({ results: this.results });
  }
  /** A one-shot utterance: final result, then the end of the session. */
  hear(text: string) {
    this.say(text, true);
    this.end();
  }
  fail(error: string) {
    this.onerror?.({ error });
    this.end();
  }
}

class FakeUtterance {
  lang = "";
  voice: unknown = null;
  onend: (() => void) | null = null;
  onerror: ((event: { error: string }) => void) | null = null;
  constructor(public text: string) {}
}

/** speechSynthesis as Chrome behaves: a queue; cancel() errors every queued utterance with "interrupted". */
const synth = {
  queue: [] as FakeUtterance[],
  spokenAll: [] as string[],
  speak: vi.fn((u: FakeUtterance) => {
    synth.queue.push(u);
    synth.spokenAll.push(u.text);
  }),
  cancel: vi.fn(() => {
    const cancelled = synth.queue.splice(0);
    cancelled.forEach((u) => u.onerror?.({ error: "interrupted" }));
  }),
  getVoices: () => [{ lang: "en-IN" }],
  /** The utterance at the head of the queue finishes playing. */
  finishOne() {
    const u = synth.queue.shift();
    u?.onend?.();
  },
  finishAll() {
    while (synth.queue.length) synth.finishOne();
  },
};

const send = vi.fn();
const latest = () => FakeRecognition.instances[FakeRecognition.instances.length - 1]!;
const voice = () => useVoiceChat.getState();
// A long answer of plain sentences: all of it is spoken, in many utterances (bullet reasons would be shortened).
const LONG = Array.from({ length: 12 }, (_, i) =>
  `Finding ${i + 1}: the rice blast weather window covered ${i + 2} of the last seven days in this farmland.`).join("\n");
const RANKING = "#1 Bishnupur farmland near Nambol: HIGH, 71/100 (confidence low).\nPLACEHOLDER thresholds: prototype scores.";

function reply(text: string): ChatMessage {
  return { id: `r${send.mock.calls.length}`, role: "assistant", kind: "answer", text, via: "voice" };
}

/** Start Voice Chat, ask a question, and wait until its answer is being spoken. */
async function askAndSpeak(question: string, answer: string) {
  send.mockResolvedValueOnce(reply(answer));
  if (voice().status === "idle") voice().start();
  latest().hear(question);
  await vi.waitFor(() => expect(voice().status).toBe("speaking"));
  synth.cancel.mockClear(); // speak() clears any earlier speech first; count only cancellations from here on
}

beforeEach(() => {
  FakeRecognition.instances = [];
  synth.queue = [];
  synth.spokenAll = [];
  synth.speak.mockClear();
  synth.cancel.mockClear();
  send.mockReset();
  vi.stubGlobal("webkitSpeechRecognition", FakeRecognition);
  vi.stubGlobal("speechSynthesis", synth);
  vi.stubGlobal("SpeechSynthesisUtterance", FakeUtterance);
  useChatStore.setState({ open: false, send });
  useVoiceChat.setState({ status: "idle", hearing: "", notice: null });
});

afterEach(() => {
  voice().stop();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("echo filter", () => {
  const spoken = "Number 1 Jiribam farmland near Kamaranga: HIGH, 71 out of 100 (confidence low). PLACEHOLDER thresholds.";
  it("recognises the app's own voice, even partly misheard", () => {
    expect(isEcho("jiribam farmland near kamaranga", spoken)).toBe(true);
    expect(isEcho("number one jiribam farmland near", spoken)).toBe(true);
    expect(isEcho("71 out of 100 confidence low", spoken)).toBe(true);
  });
  it("hears the user, even when they repeat words of the answer", () => {
    expect(isEcho("stop", spoken)).toBe(false);
    expect(isEcho("what about thoubal", spoken)).toBe(false);
    expect(isEcho("why is jiribam high", spoken)).toBe(false);
  });
});

describe("Voice Chat", () => {
  it("one click starts listening in English and opens the conversation", () => {
    voice().start();
    expect(voice().status).toBe("listening");
    expect(latest()).toMatchObject({ started: true, lang: "en-IN", continuous: false });
    expect(useChatStore.getState().open).toBe(true);
  });

  it("A: a whole answer is spoken, then it listens again by itself", async () => {
    await askAndSpeak("Which areas are at high risk?", RANKING);
    expect(send).toHaveBeenCalledWith("Which areas are at high risk?", "voice");
    expect(synth.spokenAll.join(" ")).toContain("71 out of 100");
    expect(synth.spokenAll.join(" ")).toContain("PLACEHOLDER thresholds");
    expect(latest()).toMatchObject({ continuous: true, interimResults: true, started: true }); // barge-in listener
    expect(liveRecognisers()).toBe(1);

    synth.finishAll();
    expect(voice().status).toBe("listening");
    expect(latest()).toMatchObject({ continuous: false, started: true }); // a fresh turn, no click needed
    expect(liveRecognisers()).toBe(1);
  });

  it("B: speaking is cancelled at the user's first words, before their sentence is finished", async () => {
    await askAndSpeak("Which areas are at high risk?", LONG);
    synth.finishOne(); // a second or so of the answer
    const bargeIn = latest();
    bargeIn.say("stop"); // interim: the sentence is not over

    expect(synth.cancel).toHaveBeenCalledTimes(1);
    expect(synth.queue).toHaveLength(0);
    expect(voice().status).toBe("listening");
    expect(voice().hearing).toBe("stop");
    expect(send).toHaveBeenCalledTimes(1); // nothing sent until the user finishes
    expect(FakeRecognition.instances).toHaveLength(2); // the cancelled answer's callbacks started nothing
  });

  it("C and D: interrupting mid-answer captures the whole new question and answers it instead", async () => {
    await askAndSpeak("Which areas are at high risk?", LONG);
    for (let i = 0; i < 3; i += 1) synth.finishOne(); // halfway through
    const bargeIn = latest();
    const spokenBefore = synth.spokenAll.length;

    send.mockResolvedValueOnce(reply("Thoubal farmland near Chaobok: MODERATE, 36/100."));
    bargeIn.say("stop what about");
    expect(synth.cancel).toHaveBeenCalled();
    bargeIn.say("stop what about thoubal", true); // final: the utterance is complete

    await vi.waitFor(() => expect(voice().status).toBe("speaking"));
    expect(send).toHaveBeenLastCalledWith("what about thoubal", "voice"); // the question, without the "stop"
    const newSpeech = synth.spokenAll.slice(spokenBefore).join(" ");
    expect(newSpeech).toContain("Thoubal");
    expect(newSpeech).not.toContain("Finding"); // nothing more of the old answer
  });

  it("'Stop. What about Bishnupur?' asks the question; a bare 'Stop.' asks nothing and listens again", async () => {
    await askAndSpeak("Which areas are at high risk?", LONG);
    send.mockResolvedValueOnce(reply("Bishnupur: LOW, 29/100."));
    latest().say("Stop. What about Bishnupur?", true);
    await vi.waitFor(() => expect(send).toHaveBeenLastCalledWith("What about Bishnupur?", "voice"));

    await vi.waitFor(() => expect(voice().status).toBe("speaking"));
    latest().say("stop", true);
    expect(synth.queue).toHaveLength(0); // stopped at once
    expect(voice().status).toBe("listening");
    expect(send).toHaveBeenCalledTimes(2); // "stop" alone was not sent as a question
    expect(latest()).toMatchObject({ continuous: false, started: true });
  });

  it("E: repeated interruptions keep one listener, one answer playing, and a working loop", async () => {
    await askAndSpeak("Which areas are at high risk?", LONG);
    for (const question of ["what about thoubal", "and kakching please", "why is bishnupur high"]) {
      const answer = `${question}: LOW, 20/100. ${LONG}`;
      send.mockResolvedValueOnce(reply(answer));
      latest().say(question, true);
      await vi.waitFor(() => expect(send).toHaveBeenLastCalledWith(question, "voice"));
      await vi.waitFor(() => expect(voice().status).toBe("speaking"));
      expect(liveRecognisers()).toBe(1);
      expect(synth.queue.map((u) => u.text)).toEqual(chunks(speakable(answer))); // only the new answer is queued
    }
    expect(send).toHaveBeenCalledTimes(4);
    synth.finishAll();
    expect(voice().status).toBe("listening");
    expect(liveRecognisers()).toBe(1);
  });

  it("F: Stop while speaking ends speech and listening, and nothing restarts afterwards", async () => {
    await askAndSpeak("Which areas are at high risk?", LONG);
    const bargeIn = latest();
    const count = FakeRecognition.instances.length;
    voice().stop();

    expect(synth.cancel).toHaveBeenCalled();
    expect(synth.queue).toHaveLength(0);
    expect(voice().status).toBe("idle");
    expect(liveRecognisers()).toBe(0);
    bargeIn.say("hello there", true); // a late result from the stopped listener
    bargeIn.end();
    expect(FakeRecognition.instances).toHaveLength(count);
    expect(send).toHaveBeenCalledTimes(1);
    expect(voice().status).toBe("idle");
  });

  it("F: an answer that arrives after Stop is never spoken", async () => {
    let deliver: (m: ChatMessage) => void = () => {};
    send.mockReturnValueOnce(new Promise<ChatMessage>((resolve) => (deliver = resolve)));
    voice().start();
    latest().hear("Which areas are at high risk?");
    expect(voice().status).toBe("processing");
    voice().stop();
    deliver(reply(RANKING));
    await Promise.resolve();
    await Promise.resolve();
    expect(synth.speak).not.toHaveBeenCalled();
    expect(voice().status).toBe("idle");
  });

  it("G: leaving the conversation while speaking ends Voice Chat", async () => {
    await askAndSpeak("Which areas are at high risk?", LONG);
    useChatStore.getState().setOpen(false);
    expect(voice().status).toBe("idle");
    expect(synth.queue).toHaveLength(0);
    expect(liveRecognisers()).toBe(0);
  });

  it("H: the app's own voice never interrupts it", async () => {
    await askAndSpeak("Which areas are at high risk?", RANKING);
    const bargeIn = latest();
    bargeIn.say("number 1 bishnupur farmland near");
    bargeIn.say("number 1 bishnupur farmland near nambol high 71 out of 100", true);
    bargeIn.say("farm"); // one misheard word is not enough either
    expect(synth.cancel).not.toHaveBeenCalled();
    expect(voice().status).toBe("speaking");
    expect(voice().hearing).toBe("");

    synth.finishAll();
    expect(voice().status).toBe("listening");
    expect(send).toHaveBeenCalledTimes(1); // the echo was never sent as a question
  });

  it("keeps listening for an interruption when the browser ends the listener on silence", async () => {
    await askAndSpeak("Which areas are at high risk?", LONG);
    const first = latest();
    first.fail("no-speech");
    expect(latest()).not.toBe(first);
    expect(latest()).toMatchObject({ continuous: true, started: true });
    expect(voice().status).toBe("speaking");
    expect(liveRecognisers()).toBe(1);
  });

  it("an interrupted utterance that never ends is closed after a bounded time", async () => {
    await askAndSpeak("Which areas are at high risk?", LONG);
    vi.useFakeTimers();
    send.mockResolvedValueOnce(reply("Thoubal: MODERATE, 36/100."));
    latest().say("what about thoubal"); // interim only, and the browser never finalises it
    expect(voice().status).toBe("listening");
    vi.advanceTimersByTime(8000);
    vi.useRealTimers();
    await vi.waitFor(() => expect(send).toHaveBeenLastCalledWith("what about thoubal", "voice"));
  });

  it("pauses after two turns without speech", () => {
    voice().start();
    latest().fail("no-speech");
    expect(voice().status).toBe("listening");
    latest().fail("no-speech");
    expect(voice()).toMatchObject({ status: "idle", notice: PAUSED });
    expect(send).not.toHaveBeenCalled();
  });

  it("stops with an error when the microphone is blocked", () => {
    voice().start();
    latest().fail("not-allowed");
    expect(voice()).toMatchObject({ status: "error", notice: BLOCKED });
    expect(liveRecognisers()).toBe(0);
  });

  it("explains instead of starting when the browser cannot do it", () => {
    vi.stubGlobal("webkitSpeechRecognition", undefined);
    voice().start();
    expect(voice()).toMatchObject({ status: "error", notice: UNSUPPORTED });
  });
});
