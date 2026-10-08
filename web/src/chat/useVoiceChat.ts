/** Voice Chat (v1, English): one click starts a hands-free conversation in the browser, which the user can interrupt.
 *
 *    IDLE -> LISTENING -> PROCESSING (the Conversation pipeline, unchanged) -> SPEAKING -> LISTENING ...
 *    SPEAKING -> user speech -> INTERRUPTING (speech cancelled at once, turn invalidated) -> LISTENING -> PROCESSING ...
 *
 *  Speech recognition and speech output are the browser's own (Web Speech API; Chrome and Edge recognise speech, and
 *  in Chrome the audio is processed by Google's servers). Every turn is also written to the conversation.
 *
 *  Lifecycle rules (each one fixes a failure seen in use):
 *  - ONE recognition session for the whole voice chat, continuous, restarted only after the browser itself has ended
 *    it. Phases never stop and start the microphone, so no word is lost in a hand-over and no two sessions overlap.
 *  - The app decides when the user has finished (ENDPOINT_MS of quiet after their words), not the browser's first
 *    pause: "Okay, ... what about Thoubal?" stays one utterance.
 *  - Echo: the browser gives recognition no echo cancellation, and its speechstart event fires on any sound, the app's
 *    own voice included. So the app's words are removed run by run from what is heard (`userWords`); what remains is
 *    the user. An interruption needs two such words (or one word like "stop") in two successive results, or in a
 *    final one: a single misheard word of the app's own voice cannot cut it off.
 *  - Turns: `generation` grows with every user turn, interruption, stop and start. Every asynchronous step (an
 *    answer arriving, an utterance ending, a timer) carries the generation it began in and does nothing if it is no
 *    longer current. Utterance handlers are also detached before speech is cancelled.
 *  - ONE cancellation path (`cancelSpeech`) and ONE state-change path (`transition`, which refuses invalid moves).
 *  - Speech that ends without an end event (browsers can drop it) is noticed by a watchdog.
 *
 *  Debug log: localStorage "ag04.voiceDebug" = "1" prints every step as [VOICE] lines. */

import { create } from "zustand";
import { useAppStore } from "../state/useAppStore";
import { chunks, speakable } from "./speakable";
import { useChatStore } from "./useChatStore";

export type VoiceStatus = "idle" | "listening" | "processing" | "speaking" | "interrupting" | "error";

export const VOICE_LANG = "en-IN";
export const UNSUPPORTED = "Voice Chat needs speech recognition and speech output; use Chrome or Edge.";
export const BLOCKED = "Microphone access was blocked. Allow it in the browser to use Voice Chat.";
export const PAUSED = "Voice Chat paused: no speech was heard. Click Voice Chat to continue.";
export const UNSTABLE = "Voice Chat stopped: the microphone kept disconnecting. Click Voice Chat to try again.";
/** Quiet after the user's last words before their utterance is taken as finished. */
export const ENDPOINT_MS = 900;
/** The same, when the browser has only given an unfinished (interim) transcript. */
export const INTERIM_ENDPOINT_MS = 2000;
/** Listening this long without hearing the user pauses Voice Chat. */
export const LISTEN_IDLE_MS = 15000;
/** Speech output silent for this long while SPEAKING counts as finished (an end event can be lost). */
export const SPEECH_WATCHDOG_MS = 750;
/** One word is enough to interrupt only when it is one of these. */
export const INTERRUPT_WORDS = new Set(["stop", "wait", "hold", "cancel", "pause", "no", "hey", "sorry", "excuse"]);
const RESTART_WINDOW_MS = 5000;
const MAX_RESTARTS_IN_WINDOW = 6;

const ALLOWED: Record<VoiceStatus, VoiceStatus[]> = {
  idle: ["listening", "error"],
  listening: ["processing", "idle", "error"],
  processing: ["speaking", "listening", "idle", "error"],
  speaking: ["listening", "interrupting", "idle", "error"],
  interrupting: ["listening", "idle", "error"],
  error: ["listening", "idle"],
};

// ----------------------------------------------------------------------------------------- browser speech APIs

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

// ----------------------------------------------------------------------------------------- words and echo

export function words(text: string): string[] {
  return text.toLowerCase().match(/[a-z0-9]+/g) ?? [];
}

/** What the user said in a heard phrase: the phrase without every run of two or more words that the app has just
 *  spoken (its echo through the speakers), with the user's own words kept as they were heard (case, punctuation).
 *  A lone word that the app also spoke counts as echo. */
export function userWords(heard: string, spoken: string[]): string {
  const tokens = heard.trim().split(/\s+/).filter(Boolean);
  const said = tokens.map((t) => t.toLowerCase().replace(/[^a-z0-9]/g, ""));
  const sources = spoken.map(words).filter((s) => s.length);
  const echo = said.map((w) => !w); // a token of punctuation alone is never the user's word
  for (const source of sources) {
    for (let i = 0; i < said.length; i += 1) {
      for (let j = 0; j < source.length; j += 1) {
        let k = 0;
        while (i + k < said.length && j + k < source.length && said[i + k] === source[j + k]) k += 1;
        if (k >= 2) for (let m = i; m < i + k; m += 1) echo[m] = true;
      }
    }
  }
  const kept = tokens.filter((_, i) => !echo[i]);
  const keptWords = said.filter((_, i) => !echo[i]);
  if (keptWords.length === 1 && !INTERRUPT_WORDS.has(keptWords[0]!) && sources.some((s) => s.includes(keptWords[0]!))) {
    return "";
  }
  return kept.join(" ");
}

/** Whether a phrase heard while the app speaks is entirely its own voice. */
export function isEcho(heard: string, spoken: string): boolean {
  return !userWords(heard, [spoken]);
}

const LEADING_INTERRUPTION =
  /^(?:(?:stop|wait|hold on|hold|cancel|pause|no|hey|sorry|excuse me|okay|ok)\b[\s,.!?]*)+/i;

/** The question in what was said: "Stop. What about Bishnupur?" asks "What about Bishnupur?"; "Stop." asks nothing. */
export function questionPart(text: string): string {
  return text.trim().replace(LEADING_INTERRUPTION, "").trim();
}

function enoughToInterrupt(text: string): boolean {
  const heard = words(text);
  return heard.length >= 2 || INTERRUPT_WORDS.has(heard[0] ?? "");
}

// ----------------------------------------------------------------------------------------- debug log

export interface VoiceEvent {
  at: number;
  generation: number;
  status: VoiceStatus;
  event: string;
}
const trace: VoiceEvent[] = [];

/** The last 200 lifecycle events (for tests and the debug log). */
export function voiceTrace(): VoiceEvent[] {
  return [...trace];
}

function debugEnabled(): boolean {
  try {
    return globalThis.localStorage?.getItem("ag04.voiceDebug") === "1";
  } catch {
    return false;
  }
}

// ----------------------------------------------------------------------------------------- the voice controller

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
/** The current turn generation: work begun in an older generation must do nothing. */
let generation = 0;

// The one recognition session.
let recognition: Recognition | null = null;
let recognitionEnding = false; // aborted, its end event not seen yet
let restartWhenEnded = false;
let restarts: number[] = [];
let resultsSeen = 0; // results in the current session
let lastResultFinal = true; // whether the newest result is finished (an unfinished one may still grow)
let resultsBase = 0; // the first result of the current user utterance (or of the current answer's echo)

// The current user utterance.
let carried = ""; // words kept across a session restart, or an utterance resumed after PROCESSING
let utterance = "";
let candidateHits = 0; // successive results with user words while SPEAKING
let lastCommitted = "";

// The current answer.
let spokenAnswers: string[] = []; // the answer being spoken and the one before it (echo sources)
let utterances: SpeechSynthesisUtterance[] = []; // kept referenced: a discarded utterance may never fire onend

// Timers.
let endpointTimer: ReturnType<typeof setTimeout> | null = null;
let idleTimer: ReturnType<typeof setTimeout> | null = null;
let watchdog: ReturnType<typeof setInterval> | null = null;

/** For tests: how many recognition sessions are live (never more than one). */
export function liveRecognisers(): number {
  return recognition && !recognitionEnding ? 1 : 0;
}

function clearTimer(timer: ReturnType<typeof setTimeout> | null) {
  if (timer) clearTimeout(timer);
  return null;
}

export const useVoiceChat = create<VoiceState>((set, get) => {
  function log(event: string) {
    const entry = { at: Date.now(), generation, status: get().status, event };
    trace.push(entry);
    if (trace.length > 200) trace.shift();
    if (debugEnabled()) console.debug(`[VOICE] gen ${generation} ${get().status.toUpperCase()}: ${event}`);
  }

  /** The only way the status changes. */
  function transition(next: VoiceStatus, reason: string): boolean {
    const now = get().status;
    if (now === next) return true;
    if (next !== "idle" && !ALLOWED[now].includes(next)) {
      log(`refused ${now} -> ${next} (${reason})`);
      return false;
    }
    set({ status: next });
    log(`${now} -> ${next} (${reason})`);
    return true;
  }

  // ------------------------------------------------------------------ speech output

  /** The one place speech is cancelled: handlers detached first, so no cancelled utterance can call back. */
  function cancelSpeech(reason: string) {
    watchdog = watchdog ? (clearInterval(watchdog), null) : null;
    for (const u of utterances) {
      u.onend = null;
      u.onerror = null;
    }
    utterances = [];
    const synth = synthesis();
    if (synth && (synth.speaking || synth.pending)) log(`speech cancelled (${reason})`);
    synth?.cancel();
  }

  function speak(text: string, gen: number) {
    const synth = synthesis();
    if (!active || gen !== generation || !synth) return log("stale answer ignored");
    cancelSpeech("new answer"); // never two answers at once
    const spokenText = speakable(text);
    const parts = chunks(spokenText);
    spokenAnswers = [spokenText, spokenAnswers[0] ?? ""].filter(Boolean);
    resultsBase = resultsSeen; // what is heard from now on is either the echo or a new user utterance
    candidateHits = 0;
    if (!parts.length) return startListening("nothing to say");
    if (!transition("speaking", "answer ready")) return;
    const voice = pickVoice(synth);
    synth.resume(); // a browser can leave speech paused after a cancel
    utterances = parts.map((part, index) => {
      const u = new SpeechSynthesisUtterance(part);
      u.lang = VOICE_LANG;
      if (voice) u.voice = voice;
      if (index === parts.length - 1) {
        u.onend = () => speechFinished(gen, "last utterance ended");
        u.onerror = (event) => {
          if (event.error === "interrupted" || event.error === "canceled") return; // cancellation is not an ending
          speechFinished(gen, `speech error ${event.error}`);
        };
      }
      return u;
    });
    utterances.forEach((u) => synth.speak(u));
    log(`speaking ${parts.length} utterance(s)`);
    let silentFor = 0;
    watchdog = setInterval(() => {
      if (gen !== generation || get().status !== "speaking") return;
      silentFor = synth.speaking || synth.pending ? 0 : silentFor + 250;
      if (silentFor >= SPEECH_WATCHDOG_MS) speechFinished(gen, "watchdog: speech output went silent");
    }, 250);
    ensureRecognition();
  }

  /** A natural end of the current answer: the only SPEAKING -> LISTENING move without the user speaking. */
  function speechFinished(gen: number, reason: string) {
    if (!active || gen !== generation || get().status !== "speaking") return log(`ignored: ${reason} (stale)`);
    watchdog = watchdog ? (clearInterval(watchdog), null) : null;
    utterances = [];
    // The answer's echo is not the user's next utterance; a phrase still being heard may be the user, so keep it.
    resultsBase = lastResultFinal ? resultsSeen : Math.max(0, resultsSeen - 1);
    startListening(reason);
  }

  // ------------------------------------------------------------------ listening

  /** The one path into LISTENING. The microphone is already on; this only starts a new user utterance. */
  function startListening(reason: string, keep = "") {
    if (!active || !transition("listening", reason)) return;
    carried = keep;
    utterance = keep;
    candidateHits = 0;
    endpointTimer = clearTimer(endpointTimer);
    set({ hearing: keep });
    armIdleTimer();
    ensureRecognition();
  }

  function armIdleTimer() {
    idleTimer = clearTimer(idleTimer);
    const gen = generation;
    idleTimer = setTimeout(() => {
      if (gen === generation && get().status === "listening" && !utterance.trim()) {
        log("no speech heard: pausing");
        get().stop(PAUSED);
      }
    }, LISTEN_IDLE_MS);
  }

  /** The user's utterance is finished: ask it. */
  async function commit() {
    endpointTimer = clearTimer(endpointTimer);
    idleTimer = clearTimer(idleTimer);
    const said = utterance;
    const question = questionPart(said);
    resultsBase = resultsSeen;
    carried = "";
    utterance = "";
    if (!question) {
      log(`"${said}" asks nothing: listening on`);
      startListening("only an interruption word", "");
      return;
    }
    generation += 1;
    const gen = generation;
    lastCommitted = question;
    log(`transcript: "${question}"`);
    if (!transition("processing", "utterance finished")) return;
    set({ hearing: "" });
    // A previous question may still be answered (e.g. the user went on talking): wait for it, then ask.
    for (let waited = 0; useChatStore.getState().pending || useAppStore.getState().pending; waited += 100) {
      if (gen !== generation || waited > 30000) return log("stale question dropped");
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    if (gen !== generation || !active) return log("stale question dropped");
    const reply = await useChatStore.getState().send(question, "voice");
    if (gen !== generation || !active) return log("stale answer ignored");
    speak(reply?.text ?? "No answer came back for this question.", gen);
  }

  /** Cancel the answer being spoken at once, and make everything of its turn stale. */
  function interrupt(heard: string, final: boolean) {
    log(`user speech while speaking: "${heard}"`);
    transition("interrupting", "user speech");
    generation += 1;
    log("generation invalidated");
    cancelSpeech("interrupted by the user");
    startListening("barge-in", "");
    hearUser(heard, final);
  }

  /** Words of the user, as heard so far in the current utterance. */
  function hearUser(heard: string, final: boolean) {
    utterance = [carried, heard].filter(Boolean).join(" ").trim();
    set({ hearing: utterance });
    armIdleTimer();
    endpointTimer = clearTimer(endpointTimer);
    endpointTimer = setTimeout(() => void commit(), final ? ENDPOINT_MS : INTERIM_ENDPOINT_MS);
  }

  function onResults(event: RecognitionEvent) {
    resultsSeen = event.results.length;
    lastResultFinal = !!event.results[event.results.length - 1]?.isFinal;
    if (!active) return;
    const parts: string[] = [];
    let final = event.results.length > resultsBase;
    for (let i = resultsBase; i < event.results.length; i += 1) {
      const result = event.results[i];
      const heard = userWords(result?.[0]?.transcript ?? "", spokenAnswers);
      if (heard) parts.push(heard);
      if (!result?.isFinal) final = false;
    }
    const heard = parts.join(" ").trim();
    const status = get().status;
    if (status === "speaking") {
      if (!heard || !enoughToInterrupt(heard)) {
        candidateHits = 0;
        return;
      }
      candidateHits += 1;
      const urgent = INTERRUPT_WORDS.has(words(heard)[0] ?? "");
      if (urgent || final || candidateHits >= 2) interrupt(heard, final);
      else log(`possible user speech: "${heard}" (waiting for confirmation)`);
    } else if (status === "listening") {
      if (heard) hearUser(heard, final);
    } else if (status === "processing" && heard && (final || words(heard).length >= 2)) {
      // The user went on talking: this is still their utterance, so the question being answered is stale.
      log(`user speech while processing: "${heard}"`);
      generation += 1;
      const resumed = lastCommitted;
      startListening("user went on talking", resumed);
      hearUser(heard, final);
    }
  }

  // ------------------------------------------------------------------ the one recognition session

  /** Start the session if none is running; if one is still ending, start when it has ended. */
  function ensureRecognition() {
    const Constructor = recognitionConstructor();
    if (!active || !Constructor) return;
    if (recognition) {
      if (recognitionEnding) restartWhenEnded = true;
      return;
    }
    const instance = new Constructor();
    instance.lang = VOICE_LANG;
    instance.continuous = true;
    instance.interimResults = true;
    let failure: string | null = null;
    instance.onresult = (event) => {
      if (recognition === instance) onResults(event);
    };
    instance.onerror = (event) => {
      if (recognition !== instance) return;
      failure = event.error;
      log(`recognition error: ${event.error}`);
    };
    instance.onend = () => sessionEnded(instance, failure);
    recognition = instance;
    recognitionEnding = false;
    resultsSeen = 0;
    resultsBase = 0;
    lastResultFinal = true;
    try {
      instance.start();
      log("recognition started");
    } catch {
      recognition = null;
      get().stop(BLOCKED, "error");
    }
  }

  function sessionEnded(instance: Recognition, failure: string | null) {
    if (recognition !== instance) return;
    recognition = null;
    recognitionEnding = false;
    log(`recognition ended${failure ? ` (${failure})` : ""}`);
    if (restartWhenEnded) {
      restartWhenEnded = false;
      if (active) ensureRecognition();
      return;
    }
    if (!active) return;
    if (failure === "not-allowed" || failure === "service-not-allowed" || failure === "audio-capture") {
      get().stop(BLOCKED, "error");
      return;
    }
    const now = Date.now();
    restarts = [...restarts.filter((t) => now - t < RESTART_WINDOW_MS), now];
    if (restarts.length > MAX_RESTARTS_IN_WINDOW) {
      get().stop(UNSTABLE, "error");
      return;
    }
    // The browser ends a continuous session on long silence: start a new one, keeping the words heard so far.
    if (get().status === "listening") carried = utterance;
    ensureRecognition();
  }

  function endRecognition() {
    const instance = recognition;
    if (!instance || recognitionEnding) return;
    recognitionEnding = true;
    instance.onresult = null;
    log("recognition stopping");
    try {
      instance.abort();
    } catch {
      sessionEnded(instance, null);
    }
    // If the browser never reports the end, do not let a dead session block the next start.
    setTimeout(() => {
      if (recognition === instance && recognitionEnding) sessionEnded(instance, null);
    }, 1500);
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
      generation += 1;
      restarts = [];
      spokenAnswers = [];
      set({ notice: null });
      log("voice chat started");
      useChatStore.getState().setOpen(true);
      startListening("voice chat started");
    },

    stop: (notice = null, status: VoiceStatus = "idle") => {
      const wasActive = active;
      active = false;
      generation += 1;
      cancelSpeech("voice chat stopped");
      endpointTimer = clearTimer(endpointTimer);
      idleTimer = clearTimer(idleTimer);
      restartWhenEnded = false;
      endRecognition();
      carried = "";
      utterance = "";
      set({ status, hearing: "", notice });
      if (wasActive) log(`voice chat stopped${notice ? `: ${notice}` : ""}`);
    },
  };
});

// Leaving the conversation ends Voice Chat: no voice processing continues out of sight.
useChatStore.subscribe((state, previous) => {
  if (previous.open && !state.open && active) useVoiceChat.getState().stop();
});
