import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useChatStore, type ChatMessage } from "./useChatStore";
import { BLOCKED, PAUSED, UNSUPPORTED, useVoiceChat } from "./useVoiceChat";

/** The browser's SpeechRecognition, driven by the test: each instance is one listening turn. */
class FakeRecognition {
  static instances: FakeRecognition[] = [];
  lang = "";
  continuous = true;
  interimResults = false;
  started = false;
  onresult: ((event: unknown) => void) | null = null;
  onerror: ((event: { error: string }) => void) | null = null;
  onend: (() => void) | null = null;
  constructor() {
    FakeRecognition.instances.push(this);
  }
  start() {
    this.started = true;
  }
  abort() {
    this.onend?.();
  }
  hear(text: string) {
    this.onresult?.({ results: [Object.assign([{ transcript: text }], { isFinal: true })] });
    this.onend?.();
  }
  fail(error: string) {
    this.onerror?.({ error });
    this.onend?.();
  }
}

class FakeUtterance {
  lang = "";
  voice: unknown = null;
  onend: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public text: string) {}
}

const spoken: FakeUtterance[] = [];
const synth = { speak: vi.fn((u: FakeUtterance) => spoken.push(u)), cancel: vi.fn(), getVoices: () => [{ lang: "en-IN" }] };
const send = vi.fn();
const latest = () => FakeRecognition.instances[FakeRecognition.instances.length - 1]!;
const lastSpoken = () => spoken[spoken.length - 1]!;
const status = () => useVoiceChat.getState().status;

function reply(text: string): ChatMessage {
  return { id: "r", role: "assistant", kind: "answer", text, via: "voice" };
}

beforeEach(() => {
  FakeRecognition.instances = [];
  spoken.length = 0;
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
  useVoiceChat.getState().stop();
  vi.unstubAllGlobals();
});

describe("Voice Chat", () => {
  it("one click starts listening in English and opens the conversation", () => {
    useVoiceChat.getState().start();
    expect(status()).toBe("listening");
    expect(latest()).toMatchObject({ started: true, lang: "en-IN", continuous: false });
    expect(useChatStore.getState().open).toBe(true);
  });

  it("sends what was heard through the conversation, speaks the answer, then listens again by itself", async () => {
    send.mockResolvedValue(reply("#1 Jiribam: HIGH, 71/100 (confidence low)\nPLACEHOLDER thresholds: prototype scores."));
    useVoiceChat.getState().start();
    latest().hear("Which areas are at high risk?");

    expect(send).toHaveBeenCalledWith("Which areas are at high risk?", "voice");
    await vi.waitFor(() => expect(status()).toBe("speaking"));
    const said = spoken.map((u) => u.text).join(" ");
    expect(said).toContain("71 out of 100");
    expect(said).toContain("PLACEHOLDER thresholds");
    expect(FakeRecognition.instances).toHaveLength(1); // the microphone is off while the answer is spoken

    lastSpoken().onend?.();
    expect(status()).toBe("listening");
    expect(FakeRecognition.instances).toHaveLength(2);
    expect(latest().started).toBe(true); // no second click needed
  });

  it("pauses after two turns without speech", () => {
    useVoiceChat.getState().start();
    latest().fail("no-speech");
    expect(status()).toBe("listening");
    latest().fail("no-speech");
    expect(useVoiceChat.getState()).toMatchObject({ status: "idle", notice: PAUSED });
    expect(send).not.toHaveBeenCalled();
  });

  it("stops when the microphone is blocked", () => {
    useVoiceChat.getState().start();
    latest().fail("not-allowed");
    expect(useVoiceChat.getState()).toMatchObject({ status: "idle", notice: BLOCKED });
  });

  it("stop ends speech and listening, and nothing restarts afterwards", async () => {
    send.mockResolvedValue(reply("Jiribam: HIGH, 71/100."));
    useVoiceChat.getState().start();
    latest().hear("Why?");
    await vi.waitFor(() => expect(status()).toBe("speaking"));
    useVoiceChat.getState().stop();
    expect(synth.cancel).toHaveBeenCalled();
    lastSpoken().onend?.();
    expect(status()).toBe("idle");
    expect(FakeRecognition.instances).toHaveLength(1);
  });

  it("explains instead of starting when the browser cannot do it", () => {
    vi.stubGlobal("webkitSpeechRecognition", undefined);
    useVoiceChat.getState().start();
    expect(useVoiceChat.getState()).toMatchObject({ status: "idle", notice: UNSUPPORTED });
  });
});
