import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { chunks, speakable } from "./speakable";
import { useChatStore, type ChatMessage } from "./useChatStore";
import {
  BLOCKED, classifyHeard, ECHO_TAIL_MS, ENDPOINT_MS, isEcho, LISTEN_IDLE_MS, liveRecognisers, PAUSED, questionPart,
  SPEECH_WATCHDOG_MS, UNSTABLE, UNSUPPORTED, userWords, useVoiceChat, voiceTrace, WAITING_FOR_MIC,
} from "./useVoiceChat";

/** SpeechRecognition as measured in Chrome: one continuous session; results accumulate (an interim result is
 *  replaced, a final one stays); abort() reports "aborted" and then ends, asynchronously. */
class FakeRecognition {
  static instances: FakeRecognition[] = [];
  lang = "";
  continuous = false;
  interimResults = false;
  started = false;
  track: unknown = null;
  ended = false;
  results: (Array<{ transcript: string }> & { isFinal: boolean })[] = [];
  onresult: ((event: unknown) => void) | null = null;
  onerror: ((event: { error: string }) => void) | null = null;
  onend: (() => void) | null = null;
  constructor() {
    FakeRecognition.instances.push(this);
  }
  start(track?: unknown) {
    this.started = true;
    this.track = track ?? null;
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
const INTERIM_WAIT = 2100; // INTERIM_ENDPOINT_MS and a little
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
  const spoken = "number 1 Jiribam farmland near Kamaranga: HIGH, 71 out of 100 (confidence low). Bishnupur currently has a high risk because of pest-favourable weather.";
  it("recognises the app's own voice even when recognition mishears it", () => {
    expect(isEcho("jiribam farmland near kamaranga", spoken)).toBe(true);
    expect(isEcho("number one jiribam farmland near camera anger high 71 out of 100", spoken)).toBe(true);
    expect(isEcho("vishnupur currently has a high risk because of pest favourite weather", spoken)).toBe(true);
    expect(isEcho("seventy one out of 100 confidence low", spoken)).toBe(true);
    expect(userWords("number one jiribam farmland near camera anger", [spoken])).toBe(""); // no misheard leftovers
  });
  it("hears the user, even when the question reuses words of the answer", () => {
    expect(classifyHeard("What about Bishnupur?", [spoken])).toEqual({ kind: "user", text: "What about Bishnupur?" });
    expect(classifyHeard("What about Thoubal?", [spoken]).kind).toBe("user");
    expect(classifyHeard("Why is Bishnupur high risk?", [spoken]).kind).toBe("user");
    expect(classifyHeard("stop", [spoken]).kind).toBe("user");
    expect(classifyHeard("farmland", [spoken]).kind).toBe("unclear"); // one word of the answer: too little to tell
    expect(classifyHeard("a high risk what about thoubal please", [spoken]))
      .toEqual({ kind: "user", text: "what about thoubal please" }); // an echo fragment inside is removed
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

  it("a phrase mixing a little of the app's voice with the user's is cut down to the user's words", async () => {
    await askAndSpeak("Which areas are at high risk?", LONG);
    send.mockResolvedValueOnce(reply("Thoubal: MODERATE."));
    mic().say("a high risk what about thoubal please", true); // final, mostly the user: interrupts at once
    expect(voice().status).toBe("listening");
    mic().say("because the rice blast window", true); // the cancelled answer's last echo, arriving late
    await vi.advanceTimersByTimeAsync(ENDPOINT_MS + 10);
    expect(send).toHaveBeenLastCalledWith("what about thoubal please", "voice");
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

/** What the microphone hears of the app's own voice through speakers: recognition never returns it word for word. */
const MISHEARD: [RegExp, string][] = [
  [/kamaranga/gi, "camera anger"], [/bishnupur/gi, "vishnupur"], [/favourable/gi, "favourite"],
  [/nambol/gi, "numbal"], [/thoubal/gi, "the ball"], [/chaobok/gi, "chow bok"], [/\b1\b/g, "one"],
  [/placeholder/gi, "place holder"],
];
function echoOf(spoken: string): string {
  let heard = spoken.toLowerCase().replace(/[^a-z0-9\s-]/g, " ");
  for (const [pattern, misheard] of MISHEARD) heard = heard.replace(pattern, misheard);
  const all = heard.split(/\s+/).filter(Boolean);
  return all.filter((_, i) => i % 7 !== 3).join(" "); // and a dropped word now and then
}
/** Play the whole answer through "speakers": each utterance is heard back (unfinished, then finished). */
function playWithEcho(options: { last?: "interim" } = {}) {
  while (synth.queue.length) {
    const playing = synth.queue[0]!;
    const echo = echoOf(playing.text);
    const half = echo.split(" ").slice(0, Math.ceil(echo.split(" ").length / 2)).join(" ");
    mic().say(half);
    if (synth.queue.length === 1 && options.last === "interim") {
      synth.finishOne(); // the answer ends while its last words are still being recognised
      mic().say(echo, true);
      return;
    }
    mic().say(echo, true);
    synth.finishOne();
  }
}

describe("the app's own voice is never taken for the user (speakers)", () => {
  it("1: a whole answer heard back through the speakers: no interruption, no transcript, no second request", async () => {
    await askAndSpeak("Which areas are at high risk?", LONG);
    playWithEcho({ last: "interim" });
    await vi.advanceTimersByTimeAsync(ENDPOINT_MS + INTERIM_WAIT);
    expect(synth.cancel).not.toHaveBeenCalled();
    expect(voice().status).toBe("listening");
    expect(voice().hearing).toBe("");
    expect(send).toHaveBeenCalledTimes(1);
  });

  it("2: again on the next answer, and across turns", async () => {
    await askAndSpeak("Which areas are at high risk?", RANKING);
    playWithEcho({ last: "interim" });
    send.mockResolvedValueOnce(reply(LONG));
    await userSays("Why is Bishnupur flagged?");
    expect(voice().status).toBe("speaking");
    playWithEcho({ last: "interim" });
    await vi.advanceTimersByTimeAsync(ENDPOINT_MS + INTERIM_WAIT);
    expect(send.mock.calls.map((c) => c[0])).toEqual(["Which areas are at high risk?", "Why is Bishnupur flagged?"]);
    expect(voice().status).toBe("listening");
  });

  it("3: a real interruption amid the echo is taken, and its transcript is the user's", async () => {
    await askAndSpeak("Which areas are at high risk?", LONG);
    mic().say(echoOf(synth.queue[0]!.text), true); // the echo is heard first: the app knows it plays on speakers
    synth.finishOne();
    send.mockResolvedValueOnce(reply("Thoubal farmland near Chaobok: MODERATE, 36/100."));
    mic().say("What about");
    mic().say("What about Thoubal");
    expect(synth.cancel).not.toHaveBeenCalled(); // on speakers, two words are not enough yet
    mic().say("What about Thoubal?", true);
    expect(synth.cancel).toHaveBeenCalledTimes(1);
    expect(voice().status).toBe("listening");
    await vi.advanceTimersByTimeAsync(ENDPOINT_MS + 10);
    expect(send).toHaveBeenLastCalledWith("What about Thoubal?", "voice");
    expect(voice().status).toBe("speaking");
  });

  it("4: 'What about Bishnupur?' over an answer about Bishnupur is the user, not echo", async () => {
    await askAndSpeak("Which areas are at high risk?", "Bishnupur currently has a high risk because of pest-favourable weather.");
    mic().say("vishnupur currently has a high risk"); // the echo, heard
    send.mockResolvedValueOnce(reply("Bishnupur: HIGH, 71/100."));
    mic().say("What about Bishnupur?", true);
    expect(voice().status).toBe("listening");
    await vi.advanceTimersByTimeAsync(ENDPOINT_MS + 10);
    expect(send).toHaveBeenLastCalledWith("What about Bishnupur?", "voice");
  });

  it("5: a silent user: the answer finishes and nothing is asked", async () => {
    await askAndSpeak("Which areas are at high risk?", RANKING);
    playWithEcho();
    await vi.advanceTimersByTimeAsync(LISTEN_IDLE_MS - 1000);
    expect(send).toHaveBeenCalledTimes(1);
    expect(voice().status).toBe("listening");
  });

  it("6: several turns with echo and a follow-up: only the user's three questions are asked", async () => {
    await askAndSpeak("Which area has the highest risk?", RANKING);
    playWithEcho({ last: "interim" });
    send.mockResolvedValueOnce(reply(`Thoubal farmland near Chaobok: MODERATE, 36/100. ${LONG}`));
    await userSays("What about Thoubal?");
    synth.cancel.mockClear(); // speak() clears earlier speech when an answer starts; count only what follows
    mic().say(echoOf(synth.queue[0]!.text), true);
    synth.finishOne();
    send.mockResolvedValueOnce(reply("Thoubal: MODERATE because of recent pest reports."));
    mic().say("Why?"); // one word, on speakers: not an interruption
    expect(synth.cancel).not.toHaveBeenCalled();
    playWithEcho();
    await userSays("Why?");
    playWithEcho();
    await vi.advanceTimersByTimeAsync(ENDPOINT_MS + INTERIM_WAIT);
    expect(send.mock.calls.map((c) => c[0])).toEqual(["Which area has the highest risk?", "What about Thoubal?", "Why?"]);
  });

  it("a one-word question is asked once the app is quiet, even if the answer contained that word", async () => {
    await askAndSpeak("Why is Bishnupur flagged?", ["Bishnupur: LOW, 29/100.", "Why:", "- 7 SAMPLE pest reports in the last 14 days."].join("\n"));
    playWithEcho();
    mic().say("why", true); // just after the answer: may be its echo ("Why:")
    await vi.advanceTimersByTimeAsync(ENDPOINT_MS + 10);
    expect(send).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(ECHO_TAIL_MS);
    send.mockResolvedValueOnce(reply("Bishnupur is LOW because ..."));
    await userSays("Why?"); // the app has been quiet: this is the user
    expect(send).toHaveBeenLastCalledWith("Why?", "voice");
  });

  it("the hard guard: an echo phrase that reaches the end of a turn is never sent", async () => {
    await askAndSpeak("Which areas are at high risk?", RANKING);
    playWithEcho();
    mic().say("number one bishnupur farmland near nambol high", true); // late echo, after the answer ended
    await vi.advanceTimersByTimeAsync(ENDPOINT_MS + INTERIM_WAIT);
    expect(send).toHaveBeenCalledTimes(1);
  });

  it("7: Stop while speaking: audio and recognition stop, no transcript, no request, no restart", async () => {
    await askAndSpeak("Which areas are at high risk?", LONG);
    mic().say(echoOf(synth.queue[0]!.text));
    const session = mic();
    voice().stop();
    session.say(echoOf(synth.all[0]!.text), true);
    await vi.advanceTimersByTimeAsync(LISTEN_IDLE_MS + 5000);
    expect(synth.queue).toHaveLength(0);
    expect(session.ended).toBe(true);
    expect(FakeRecognition.instances).toHaveLength(1);
    expect(send).toHaveBeenCalledTimes(1);
    expect(voice()).toMatchObject({ status: "idle", hearing: "" });
  });

  it("listens on an echo-cancelled microphone track, and releases it on Stop", async () => {
    const track = { readyState: "live", stop: vi.fn(), getSettings: () => ({ echoCancellation: true }) };
    const stream = { getAudioTracks: () => [track], getTracks: () => [track] };
    const getUserMedia = vi.fn().mockResolvedValue(stream);
    vi.stubGlobal("navigator", { ...globalThis.navigator, mediaDevices: { getUserMedia } });
    voice().start();
    expect(voice().notice).toBe(WAITING_FOR_MIC); // while the browser asks for the microphone
    await settle();
    expect(voice().notice).toBeNull();
    expect(getUserMedia).toHaveBeenCalledWith({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    expect(mic().track).toBe(track);
    expect(voice().status).toBe("listening");
    voice().stop();
    expect(track.stop).toHaveBeenCalled();
  });

  it("a blocked microphone (getUserMedia refused) stops with an error", async () => {
    const refused = Object.assign(new Error("denied"), { name: "NotAllowedError" });
    vi.stubGlobal("navigator", { ...globalThis.navigator, mediaDevices: { getUserMedia: vi.fn().mockRejectedValue(refused) } });
    voice().start();
    await settle();
    expect(voice()).toMatchObject({ status: "error", notice: BLOCKED });
    expect(FakeRecognition.instances).toHaveLength(0);
  });
});
