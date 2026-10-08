import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { chunks, speakable } from "./speakable";
import { useChatStore, type ChatMessage } from "./useChatStore";
import {
  BLOCKED, ENDPOINT_MS, isEcho, LISTEN_IDLE_MS, liveRecognisers, PAUSED, questionPart, SPEECH_WATCHDOG_MS,
  UNSTABLE, UNSUPPORTED, userWords, useVoiceChat, voiceTrace,
} from "./useVoiceChat";

/** SpeechRecognition as measured in Chrome: one continuous session; results accumulate (an interim result is
 *  replaced, a final one stays); abort() reports "aborted" and then ends, asynchronously. */
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
    queueMicrotask(() => this.end());
  }
  abort() {
    queueMicrotask(() => {
      this.onerror?.({ error: "aborted" });
      this.end();
    });
  }
  end() {
    if (this.ended) return;
    this.ended = true;
    this.onend?.();
  }
  /** What the microphone hears: updates the unfinished result, or adds one. */
  say(text: string, final = false) {
    if (this.ended) return;
    const last = this.results[this.results.length - 1];
    const result = Object.assign([{ transcript: text }], { isFinal: final });
    if (last && !last.isFinal) this.results[this.results.length - 1] = result;
    else this.results.push(result);
    this.onresult?.({ results: this.results });
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
  all: [] as FakeUtterance[],
  get speaking() {
    return synth.queue.length > 0;
  },
  get pending() {
    return synth.queue.length > 1;
  },
  speak: vi.fn((u: FakeUtterance) => {
    synth.queue.push(u);
    synth.all.push(u);
  }),
  cancel: vi.fn(() => synth.queue.splice(0).forEach((u) => u.onerror?.({ error: "interrupted" }))),
  resume: vi.fn(),
  getVoices: () => [{ lang: "en-IN" }],
  finishOne(fireEnd = true) {
    const u = synth.queue.shift();
    if (fireEnd) u?.onend?.();
  },
  finishAll(fireEnd = true) {
    while (synth.queue.length) synth.finishOne(fireEnd);
  },
};

const send = vi.fn();
const mic = () => FakeRecognition.instances[FakeRecognition.instances.length - 1]!;
const voice = () => useVoiceChat.getState();
const settle = () => vi.advanceTimersByTimeAsync(10);
const spokenSince = (n: number) => synth.all.slice(n).map((u) => u.text).join(" ");

// A long answer: every sentence is spoken, in many utterances.
const LONG = Array.from({ length: 14 }, (_, i) =>
  `Finding ${i + 1}: Bishnupur currently has a high risk because the rice blast window covered ${i + 2} days.`).join("\n");
const RANKING = "#1 Bishnupur farmland near Nambol: HIGH, 71/100 (confidence low).\nPLACEHOLDER thresholds: prototype scores.";

function reply(text: string): ChatMessage {
  return { id: `r${send.mock.calls.length}`, role: "assistant", kind: "answer", text, via: "voice" };
}

/** The user says a whole sentence and pauses. */
async function userSays(text: string) {
  mic().say(text, true);
  await vi.advanceTimersByTimeAsync(ENDPOINT_MS + 10);
}

/** Start (if needed), ask, and get to the point where the answer is being spoken. */
async function askAndSpeak(question: string, answer: string) {
  send.mockResolvedValueOnce(reply(answer));
  if (voice().status === "idle") voice().start();
  await userSays(question);
  expect(voice().status).toBe("speaking");
  synth.cancel.mockClear();
}

function refusedTransitions() {
  return voiceTrace().filter((e) => e.event.startsWith("refused"));
}

beforeEach(() => {
  vi.useFakeTimers();
  FakeRecognition.instances = [];
  synth.queue = [];
  synth.all = [];
  synth.speak.mockClear();
  synth.cancel.mockClear();
  send.mockReset();
  vi.stubGlobal("webkitSpeechRecognition", FakeRecognition);
  vi.stubGlobal("speechSynthesis", synth);
  vi.stubGlobal("SpeechSynthesisUtterance", FakeUtterance);
  useChatStore.setState({ open: false, pending: false, send });
  useVoiceChat.setState({ status: "idle", hearing: "", notice: null });
});

afterEach(async () => {
  voice().stop();
  await vi.advanceTimersByTimeAsync(2000);
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("words heard while the app speaks", () => {
  const spoken = "Number 1 Jiribam farmland near Kamaranga: HIGH, 71 out of 100 (confidence low). PLACEHOLDER thresholds.";
  it("removes the app's own words, run by run, and keeps the user's", () => {
    expect(isEcho("jiribam farmland near kamaranga", spoken)).toBe(true);
    expect(isEcho("71 out of 100 confidence low", spoken)).toBe(true);
    expect(userWords("jiribam farmland near what about thoubal", [spoken])).toBe("what about thoubal");
    expect(userWords("why is jiribam high", [spoken])).toBe("why is jiribam high");
    expect(userWords("farmland", [spoken])).toBe(""); // a lone word of the answer is echo
    expect(userWords("stop", [spoken])).toBe("stop");
  });
  it("finds the question in what was said", () => {
    expect(questionPart("Okay, what about Thoubal?")).toBe("what about Thoubal?");
    expect(questionPart("Stop. Wait.")).toBe("");
  });
});

describe("Voice Chat lifecycle", () => {
  it("normal turn: one continuous session, the answer spoken in full, then listening again by itself", async () => {
    await askAndSpeak("Which areas are at high risk?", RANKING);
    expect(send).toHaveBeenCalledWith("Which areas are at high risk?", "voice");
    expect(useChatStore.getState().open).toBe(true);
    expect(spokenSince(0)).toContain("71 out of 100");
    expect(spokenSince(0)).toContain("PLACEHOLDER thresholds");
    synth.finishAll();
    expect(voice().status).toBe("listening");
    expect(FakeRecognition.instances).toHaveLength(1); // the microphone was never stopped and restarted
    expect(mic()).toMatchObject({ continuous: true, interimResults: true, started: true, ended: false });
    expect(refusedTransitions()).toEqual([]);
  });

  it("a pause inside a sentence does not cut it: 'Okay, ... what about Thoubal?'", async () => {
    voice().start();
    send.mockResolvedValueOnce(reply("Thoubal: MODERATE, 36/100."));
    mic().say("okay", true);
    await vi.advanceTimersByTimeAsync(500);
    mic().say("what about thoubal", true);
    await vi.advanceTimersByTimeAsync(ENDPOINT_MS + 10);
    expect(send).toHaveBeenCalledTimes(1);
    expect(send).toHaveBeenCalledWith("what about thoubal", "voice");
  });

  it.each([
    ["at the beginning", 0],
    ["after about 3 seconds", 1],
    ["halfway through", 3],
    ["near the end", -1],
  ])("interrupting %s stops speech at the user's first words, and only their question is asked", async (_, played) => {
    await askAndSpeak("Which areas are at high risk?", LONG);
    const toPlay = played < 0 ? synth.queue.length - 1 : played;
    for (let i = 0; i < toPlay; i += 1) synth.finishOne();
    expect(voice().status).toBe("speaking");
    const before = synth.all.length;

    mic().say("what about"); // interim, first words: a candidate
    expect(synth.cancel).not.toHaveBeenCalled();
    mic().say("what about thoubal"); // confirmed by the next result: interrupt now, before the sentence ends
    expect(synth.cancel).toHaveBeenCalledTimes(1);
    expect(synth.queue).toHaveLength(0);
    expect(voice().status).toBe("listening");
    expect(voice().hearing).toBe("what about thoubal");

    send.mockResolvedValueOnce(reply("Thoubal farmland near Chaobok: MODERATE, 36/100."));
    mic().say("what about thoubal", true);
    await vi.advanceTimersByTimeAsync(ENDPOINT_MS + 10);
    expect(send).toHaveBeenLastCalledWith("what about thoubal", "voice");
    expect(voice().status).toBe("speaking");
    expect(spokenSince(before)).toContain("Thoubal");
    expect(spokenSince(before)).not.toContain("Finding"); // the old answer never resumes
    expect(FakeRecognition.instances).toHaveLength(1);
    expect(refusedTransitions()).toEqual([]);
  });

  it("'stop' interrupts at once, and alone asks nothing", async () => {
    await askAndSpeak("Which areas are at high risk?", LONG);
    mic().say("stop");
    expect(synth.queue).toHaveLength(0);
    expect(voice().status).toBe("listening");
    mic().say("stop", true);
    await vi.advanceTimersByTimeAsync(ENDPOINT_MS + 10);
    expect(send).toHaveBeenCalledTimes(1);
    expect(voice().status).toBe("listening");
  });

  it("a phrase mixing the app's voice and the user's is cut down to the user's words", async () => {
    await askAndSpeak("Which areas are at high risk?", LONG);
    send.mockResolvedValueOnce(reply("Thoubal: MODERATE."));
    mic().say("bishnupur currently has a high risk what about thoubal", true); // final: interrupts at once
    expect(voice().status).toBe("listening");
    mic().say("because the rice blast window", true); // the cancelled answer's last echo, arriving late
    await vi.advanceTimersByTimeAsync(ENDPOINT_MS + 10);
    expect(send).toHaveBeenLastCalledWith("what about thoubal", "voice");
  });

  it("the app's own voice never interrupts it", async () => {
    await askAndSpeak("Which areas are at high risk?", RANKING);
    mic().say("number 1 bishnupur farmland near");
    mic().say("number 1 bishnupur farmland near nambol high 71 out of 100", true);
    mic().say("farmland"); // one word of the answer
    mic().say("prototype scores", true);
    mic().say("barn yard"); // two misheard words, once: not confirmed
    mic().say("placeholder thresholds", true); // and gone again
    expect(synth.cancel).not.toHaveBeenCalled();
    expect(voice().status).toBe("speaking");
    synth.finishAll();
    await vi.advanceTimersByTimeAsync(ENDPOINT_MS + 10);
    expect(voice().status).toBe("listening");
    expect(send).toHaveBeenCalledTimes(1); // no echo was ever sent as a question
  });

  it("rapid repeated interruptions: one session, only the newest answer, no stuck state", async () => {
    await askAndSpeak("Which area has the highest risk?", LONG);
    for (const question of ["what about thoubal", "and kakching please", "why is bishnupur high", "what about jiribam"]) {
      const answer = `${question}: LOW, 20/100. ${LONG}`;
      send.mockResolvedValueOnce(reply(answer));
      synth.finishOne();
      mic().say(question, true);
      expect(voice().status).toBe("listening");
      await vi.advanceTimersByTimeAsync(ENDPOINT_MS + 10);
      expect(send).toHaveBeenLastCalledWith(question, "voice");
      expect(voice().status).toBe("speaking");
      expect(synth.queue.map((u) => u.text)).toEqual(chunks(speakable(answer))); // nothing of an older answer
      expect(liveRecognisers()).toBe(1);
    }
    expect(FakeRecognition.instances).toHaveLength(1);
    synth.finishAll();
    expect(voice().status).toBe("listening");
    expect(refusedTransitions()).toEqual([]);
  });

  it("a cancelled answer's end event, fired late, changes nothing", async () => {
    await askAndSpeak("Which areas are at high risk?", LONG);
    const oldLast = synth.queue[synth.queue.length - 1]!;
    const oldEnd = oldLast.onend;
    send.mockResolvedValueOnce(reply(`Thoubal: MODERATE. ${LONG}`));
    await userSays("what about thoubal");
    expect(voice().status).toBe("speaking");
    oldEnd?.(); // the browser reports the old answer's end after all
    expect(voice().status).toBe("speaking");
    expect(oldLast.onend).toBeNull(); // detached before cancelling
  });

  it("speech that ends without an end event is noticed, and listening resumes", async () => {
    await askAndSpeak("Which areas are at high risk?", RANKING);
    synth.finishAll(false); // the browser drops the end event
    await vi.advanceTimersByTimeAsync(SPEECH_WATCHDOG_MS + 300);
    expect(voice().status).toBe("listening");
  });

  it("Stop while speaking ends speech and the microphone, and nothing restarts", async () => {
    await askAndSpeak("Which areas are at high risk?", LONG);
    const session = mic();
    voice().stop();
    expect(synth.queue).toHaveLength(0);
    expect(voice().status).toBe("idle");
    await settle();
    expect(session.ended).toBe(true);
    expect(liveRecognisers()).toBe(0);
    session.say("hello there", true); // late events of the stopped session
    await vi.advanceTimersByTimeAsync(LISTEN_IDLE_MS + 5000);
    expect(FakeRecognition.instances).toHaveLength(1);
    expect(send).toHaveBeenCalledTimes(1);
    expect(voice().status).toBe("idle");
  });

  it("an answer arriving after Stop is never spoken", async () => {
    let deliver: (m: ChatMessage) => void = () => {};
    send.mockReturnValueOnce(new Promise<ChatMessage>((resolve) => (deliver = resolve)));
    voice().start();
    await userSays("Which areas are at high risk?");
    expect(voice().status).toBe("processing");
    voice().stop();
    deliver(reply(RANKING));
    await settle();
    expect(synth.speak).not.toHaveBeenCalled();
    expect(voice().status).toBe("idle");
  });

  it("switching to Conversation while speaking stops everything; Voice Chat then restarts cleanly", async () => {
    await askAndSpeak("Which areas are at high risk?", LONG);
    useChatStore.getState().setOpen(false);
    expect(voice().status).toBe("idle");
    expect(synth.queue).toHaveLength(0);
    await settle();
    expect(liveRecognisers()).toBe(0);

    voice().start(); // straight back
    await settle();
    expect(voice().status).toBe("listening");
    expect(FakeRecognition.instances).toHaveLength(2);
    expect(liveRecognisers()).toBe(1);
    send.mockResolvedValueOnce(reply(RANKING));
    await userSays("Which areas are at high risk?");
    expect(voice().status).toBe("speaking");
  });

  it("if the user goes on talking while the answer is fetched, the whole utterance is asked", async () => {
    let deliverFirst: (m: ChatMessage) => void = () => {};
    send.mockReturnValueOnce(new Promise<ChatMessage>((resolve) => (deliverFirst = resolve)));
    voice().start();
    await userSays("what about");
    expect(voice().status).toBe("processing");
    useChatStore.setState({ pending: true }); // the first question is still being answered
    mic().say("thoubal in the valley", true);
    expect(voice().status).toBe("listening");
    send.mockResolvedValueOnce(reply("Thoubal: MODERATE."));
    await vi.advanceTimersByTimeAsync(ENDPOINT_MS + 10);
    expect(send).toHaveBeenCalledTimes(1); // waits for the first to finish
    useChatStore.setState({ pending: false });
    deliverFirst(reply("Which list do you mean?"));
    await vi.advanceTimersByTimeAsync(200);
    expect(send).toHaveBeenLastCalledWith("what about thoubal in the valley", "voice");
    expect(spokenSince(0)).not.toContain("Which list"); // the stale answer is not spoken
  });

  it("a session the browser ends on silence is replaced, keeping the words heard so far", async () => {
    voice().start();
    mic().say("what about");
    const first = mic();
    first.fail("no-speech");
    expect(FakeRecognition.instances).toHaveLength(2);
    send.mockResolvedValueOnce(reply("Thoubal: MODERATE."));
    await userSays("thoubal");
    expect(send).toHaveBeenCalledWith("what about thoubal", "voice");
  });

  it("stops with an error when the microphone keeps disconnecting", async () => {
    voice().start();
    for (let i = 0; i < 8 && voice().status !== "error"; i += 1) mic().fail("network");
    expect(voice()).toMatchObject({ status: "error", notice: UNSTABLE });
  });

  it("stops with an error when the microphone is blocked", () => {
    voice().start();
    mic().fail("not-allowed");
    expect(voice()).toMatchObject({ status: "error", notice: BLOCKED });
  });

  it("pauses after listening for a while without speech", async () => {
    voice().start();
    await vi.advanceTimersByTimeAsync(LISTEN_IDLE_MS + 10);
    expect(voice()).toMatchObject({ status: "idle", notice: PAUSED });
    expect(send).not.toHaveBeenCalled();
  });

  it("explains instead of starting when the browser cannot do it", () => {
    vi.stubGlobal("webkitSpeechRecognition", undefined);
    voice().start();
    expect(voice()).toMatchObject({ status: "error", notice: UNSUPPORTED });
  });
});
