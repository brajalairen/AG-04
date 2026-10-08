/** Voice Chat (v1, English): one click starts a hands-free loop in the browser, which the user can interrupt.
 *
 *    idle -> listening -> processing (the Conversation pipeline, unchanged) -> speaking -> listening ...
 *    speaking -> the user starts talking -> interrupting (speech cancelled at once) -> listening -> processing ...
 *
 *  Speech recognition and speech output are the browser's own (Web Speech API; Chrome and Edge recognise speech, and
 *  in Chrome the audio is processed by Google's servers). Every turn is also written to the conversation.
 *
 *  Barge-in: while an answer is spoken, a second recogniser listens. The browser gives recognition no echo
 *  cancellation, so through speakers it also hears the app's own voice; a heard phrase counts as the user only when it
 *  is not a run of the words being spoken (see `isEcho`). The first such words cancel the speech, and the same
 *  recogniser keeps listening, so nothing the user said is lost. With headphones there is no echo at all.
 *
 *  Turns: every answer belongs to a numbered turn. Interrupting or stopping starts a new turn, and any callback of an
 *  older one (a cancelled utterance's onend or onerror, an answer that arrives late, a recogniser that ends late)
 *  is ignored, so a cancelled answer can never restart listening or speak over a newer one. */

import { create } from "zustand";
import { chunks, speakable } from "./speakable";
import { useChatStore } from "./useChatStore";

export type VoiceStatus = "idle" | "listening" | "processing" | "speaking" | "interrupting" | "error";

export const VOICE_LANG = "en-IN";
export const MAX_SILENT_TURNS = 2;
export const UNSUPPORTED = "Voice Chat needs speech recognition and speech output; use Chrome or Edge.";
export const BLOCKED = "Microphone access was blocked. Allow it in the browser to use Voice Chat.";
export const PAUSED = "Voice Chat paused: no speech was heard. Click Voice Chat to continue.";
/** One word is enough to interrupt only when it is one of these; otherwise two words are needed, so a single
 *  misheard word of the app's own voice cannot cut it off. */
export const INTERRUPT_WORDS = new Set(["stop", "wait", "hold", "cancel", "pause", "no", "hey", "sorry", "excuse"]);
/** After an interruption, the user's utterance is taken as finished after this long at the latest. */
export const BARGE_IN_MAX_MS = 8000;
/** How often the barge-in listener may be restarted during one answer (the browser ends it on silence). */
const MAX_BARGE_IN_RESTARTS = 10;

/** The parts of SpeechRecognition the loop uses. */
interface Recognition {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((event: RecognitionEvent) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
}
interface RecognitionEvent {
  resultIndex?: number;
  results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }>;
}
type RecognitionConstructor = new () => Recognition;

function recognitionConstructor(): RecognitionConstructor | null {
  const scope = globalThis as unknown as {
    SpeechRecognition?: RecognitionConstructor;
    webkitSpeechRecognition?: RecognitionConstructor;
  };
  return scope.SpeechRecognition ?? scope.webkitSpeechRecognition ?? null;
}

function synthesis(): SpeechSynthesis | null {
  return typeof globalThis.speechSynthesis !== "undefined" && typeof globalThis.SpeechSynthesisUtterance !== "undefined"
    ? globalThis.speechSynthesis
    : null;
}

export function voiceChatSupported(): boolean {
  return recognitionConstructor() !== null && synthesis() !== null;
}

/** An English voice, preferring Indian English. */
function pickVoice(synth: SpeechSynthesis): SpeechSynthesisVoice | null {
  const voices = synth.getVoices();
  return voices.find((v) => v.lang === VOICE_LANG) ?? voices.find((v) => v.lang.startsWith("en")) ?? null;
}

const LEADING_INTERRUPTION =
  /^(?:(?:stop|wait|hold on|hold|cancel|pause|no|hey|sorry|excuse me|okay|ok)\b[\s,.!?]*)+/i;

/** The question in what was said: "Stop. What about Bishnupur?" asks "What about Bishnupur?"; "Stop." asks nothing. */
export function questionPart(text: string): string {
  return text.trim().replace(LEADING_INTERRUPTION, "").trim();
}

export function words(text: string): string[] {
  return text.toLowerCase().match(/[a-z0-9]+/g) ?? [];
}

/** Whether a phrase heard while the app speaks is the app's own voice: most of its words form one unbroken run of
 *  the words being spoken. The user's own words ("stop", "what about Thoubal") break the run even when some of them
 *  also occur in the answer. */
export function isEcho(heard: string, spoken: string): boolean {
  const said = words(heard);
  if (!said.length) return true;
  const source = words(spoken);
  let longest = 0;
  for (let i = 0; i < source.length; i += 1) {
    for (let j = 0; j < said.length; j += 1) {
      let k = 0;
      while (i + k < source.length && j + k < said.length && source[i + k] === said[j + k]) k += 1;
      longest = Math.max(longest, k);
    }
  }
  return longest >= Math.max(1, Math.ceil(said.length * 0.6));
}

interface VoiceState {
  status: VoiceStatus;
  /** What the user is heard saying right now, for the screen. */
  hearing: string;
  /** Why the loop stopped, when it stopped on its own. */
  notice: string | null;
  start: () => void;
  stop: (notice?: string | null, status?: VoiceStatus) => void;
}

let active = false;
/** The current turn: callbacks of any older turn are ignored. */
let turn = 0;
let recognition: Recognition | null = null;
let silentTurns = 0;
let bargeInTimer: ReturnType<typeof setTimeout> | null = null;

/** Detach a recogniser's handlers before ending it, so it can call nothing back. */
function release(instance: Recognition | null) {
  if (bargeInTimer) clearTimeout(bargeInTimer);
  bargeInTimer = null;
  if (!instance) return;
  instance.onresult = null;
  instance.onerror = null;
  instance.onend = null;
  try {
    instance.abort();
  } catch {
    // already ended
  }
  if (recognition === instance) recognition = null;
}

/** For tests: how many recognisers are live (at most one at any time). */
export function liveRecognisers(): number {
  return recognition ? 1 : 0;
}

export const useVoiceChat = create<VoiceState>((set, get) => {
  const current = (myTurn: number) => active && myTurn === turn;

  /** A normal listening turn: one utterance, ended by the browser when the user stops talking. */
  function listen() {
    const Constructor = recognitionConstructor();
    if (!active || !Constructor) return;
    release(recognition);
    const myTurn = turn;
    let heard = "";
    let failed: string | null = null;
    const instance = new Constructor();
    instance.lang = VOICE_LANG;
    instance.continuous = false;
    instance.interimResults = true;
    instance.onresult = (event) => {
      if (!current(myTurn)) return;
      let interim = "";
      heard = "";
      for (let i = 0; i < event.results.length; i += 1) {
        const result = event.results[i];
        if (!result?.[0]) continue;
        if (result.isFinal) heard += result[0].transcript;
        else interim += result[0].transcript;
      }
      set({ hearing: `${heard} ${interim}`.trim() });
    };
    instance.onerror = (event) => {
      failed = event.error;
    };
    instance.onend = () => {
      if (recognition === instance) recognition = null;
      if (!current(myTurn)) return;
      finishListening(heard, failed);
    };
    recognition = instance;
    set({ status: "listening", hearing: "" });
    try {
      instance.start();
    } catch {
      get().stop(BLOCKED, "error");
    }
  }

  function finishListening(heard: string, failed: string | null) {
    if (failed === "not-allowed" || failed === "service-not-allowed" || failed === "audio-capture") {
      get().stop(BLOCKED, "error");
      return;
    }
    const text = questionPart(heard);
    if (text) {
      silentTurns = 0;
      void answer(text);
      return;
    }
    if (heard.trim()) {
      // only "stop" (or "wait", ...): the answer has stopped; listen for what comes next, asking nothing
      silentTurns = 0;
      listen();
      return;
    }
    silentTurns += 1;
    if (silentTurns >= MAX_SILENT_TURNS) get().stop(PAUSED);
    else listen();
  }

  async function answer(text: string) {
    turn += 1; // a new user turn: whatever an older turn still has pending is now stale
    const myTurn = turn;
    set({ status: "processing", hearing: "" });
    const reply = await useChatStore.getState().send(text, "voice");
    if (!current(myTurn)) return; // stopped, or interrupted, while the answer was on its way
    speak(reply?.text ?? "No answer came back for this question.", myTurn);
  }

  function speak(text: string, myTurn: number) {
    const synth = synthesis();
    if (!current(myTurn) || !synth) return;
    const spokenText = speakable(text);
    const parts = chunks(spokenText);
    if (!parts.length) {
      listen();
      return;
    }
    set({ status: "speaking", hearing: "" });
    synth.cancel();
    const voice = pickVoice(synth);
    parts.forEach((part, index) => {
      const utterance = new SpeechSynthesisUtterance(part);
      utterance.lang = VOICE_LANG;
      if (voice) utterance.voice = voice;
      if (index === parts.length - 1) {
        // A cancelled utterance also ends (or errors with "interrupted"): only the current turn may go on.
        const done = () => {
          if (!current(myTurn) || get().status !== "speaking") return;
          release(recognition); // the barge-in listener; a fresh turn listens next
          listen();
        };
        utterance.onend = done;
        utterance.onerror = done;
      }
      synth.speak(utterance);
    });
    listenForBargeIn(spokenText, myTurn, 0);
  }

  /** While an answer is spoken: listen for the user, and interrupt at their first words that are not the echo. */
  function listenForBargeIn(spokenText: string, speakingTurn: number, restarts: number) {
    const Constructor = recognitionConstructor();
    if (!current(speakingTurn) || !Constructor) return;
    release(recognition);
    let interruptedTurn: number | null = null; // the turn begun by interrupting
    let userText = "";
    let failed: string | null = null;
    const instance = new Constructor();
    instance.lang = VOICE_LANG;
    instance.continuous = true; // keeps listening through the answer's pauses
    instance.interimResults = true; // reacts to the first words, not the finished sentence
    instance.onresult = (event) => {
      const own = interruptedTurn ?? speakingTurn;
      if (!current(own)) return;
      // The user's words so far: every result that is not the app's own voice.
      const mine: string[] = [];
      let finished = false;
      for (let i = 0; i < event.results.length; i += 1) {
        const result = event.results[i];
        const said = result?.[0]?.transcript ?? "";
        if (!said.trim() || isEcho(said, spokenText)) continue;
        mine.push(said.trim());
        if (result?.isFinal) finished = true;
      }
      if (!mine.length) return;
      userText = mine.join(" ");
      if (interruptedTurn === null) {
        const heardWords = words(userText);
        if (heardWords.length < 2 && !INTERRUPT_WORDS.has(heardWords[0] ?? "")) return; // wait for one more word
        interruptedTurn = interrupt();
        // The browser normally ends the utterance on a pause; this bounds it if it does not.
        bargeInTimer = setTimeout(() => {
          if (recognition === instance) instance.stop();
        }, BARGE_IN_MAX_MS);
      }
      set({ hearing: userText });
      if (finished) instance.stop(); // the user's utterance is complete: end, then answer it (onend)
    };
    instance.onerror = (event) => {
      failed = event.error;
    };
    instance.onend = () => {
      if (recognition === instance) recognition = null;
      if (bargeInTimer) clearTimeout(bargeInTimer);
      bargeInTimer = null;
      if (interruptedTurn !== null) {
        if (current(interruptedTurn)) finishListening(userText, failed);
        return;
      }
      if (!current(speakingTurn) || get().status !== "speaking") return;
      if (failed === "not-allowed" || failed === "service-not-allowed" || failed === "audio-capture") return;
      if (restarts >= MAX_BARGE_IN_RESTARTS) return; // the answer finishes; it just cannot be interrupted any more
      listenForBargeIn(spokenText, speakingTurn, restarts + 1); // ended on silence: keep listening while speaking
    };
    recognition = instance;
    try {
      instance.start();
    } catch {
      // the answer is still spoken; it just cannot be interrupted this turn
    }
  }

  /** Cancel the answer being spoken, at once, and make every callback of its turn stale. */
  function interrupt(): number {
    set({ status: "interrupting" });
    turn += 1;
    synthesis()?.cancel();
    silentTurns = 0;
    set({ status: "listening" });
    return turn;
  }

  return {
    status: "idle",
    hearing: "",
    notice: null,

    start: () => {
      if (active) return;
      if (!voiceChatSupported()) {
        set({ status: "error", notice: UNSUPPORTED });
        return;
      }
      active = true;
      silentTurns = 0;
      turn += 1;
      set({ notice: null });
      useChatStore.getState().setOpen(true);
      listen();
    },

    stop: (notice = null, status: VoiceStatus = "idle") => {
      active = false;
      turn += 1; // nothing pending may act after a stop
      release(recognition);
      synthesis()?.cancel();
      set({ status, hearing: "", notice });
    },
  };
});

// Closing the conversation ends Voice Chat: no voice processing continues out of sight.
useChatStore.subscribe((state, previous) => {
  if (previous.open && !state.open && active) useVoiceChat.getState().stop();
});
