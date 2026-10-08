/** Voice Chat (v1, English): one click starts a hands-free loop in the browser.
 *
 *    listening -> (a sentence is heard) -> thinking: the Conversation pipeline, unchanged -> speaking -> listening ...
 *
 *  Speech recognition and speech output are the browser's own (Web Speech API; Chrome and Edge recognise speech, and
 *  in Chrome the audio is processed by Google's servers). Half-duplex: the microphone is off while an answer is
 *  spoken, so the app never hears itself. Every turn is also written to the conversation. The loop pauses after two
 *  turns without speech, and on any microphone error; nothing is ever sent without the user speaking. */

import { create } from "zustand";
import { chunks, speakable } from "./speakable";
import { useChatStore } from "./useChatStore";

export type VoiceStatus = "idle" | "listening" | "thinking" | "speaking";

export const VOICE_LANG = "en-IN";
export const MAX_SILENT_TURNS = 2;
export const UNSUPPORTED = "Voice Chat needs speech recognition and speech output; use Chrome or Edge.";
export const BLOCKED = "Microphone access was blocked. Allow it in the browser to use Voice Chat.";
export const PAUSED = "Voice Chat paused: no speech was heard. Click Voice Chat to continue.";

/** The parts of SpeechRecognition the loop uses. */
interface Recognition {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start(): void;
  abort(): void;
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
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

interface VoiceState {
  status: VoiceStatus;
  /** What is being heard right now (interim recognition), for the screen. */
  hearing: string;
  /** Why the loop stopped, when it stopped on its own. */
  notice: string | null;
  start: () => void;
  stop: (notice?: string | null) => void;
}

let active = false;
let recognition: Recognition | null = null;
let silentTurns = 0;

export const useVoiceChat = create<VoiceState>((set, get) => {
  function listen() {
    const Constructor = recognitionConstructor();
    if (!active || !Constructor) return;
    let heard = "";
    let failed: string | null = null;
    const instance = new Constructor();
    instance.lang = VOICE_LANG;
    instance.continuous = false;
    instance.interimResults = true;
    instance.onresult = (event) => {
      let interim = "";
      heard = "";
      for (let i = 0; i < event.results.length; i += 1) {
        const result = event.results[i];
        if (!result?.[0]) continue;
        if (result.isFinal) heard += result[0].transcript;
        else interim += result[0].transcript;
      }
      set({ hearing: (heard + " " + interim).trim() });
    };
    instance.onerror = (event) => {
      failed = event.error;
    };
    instance.onend = () => {
      if (recognition === instance) recognition = null;
      if (!active) return;
      if (failed === "not-allowed" || failed === "service-not-allowed" || failed === "audio-capture") {
        get().stop(BLOCKED);
        return;
      }
      const text = heard.trim();
      if (text) {
        silentTurns = 0;
        void answer(text);
        return;
      }
      silentTurns += 1;
      if (silentTurns >= MAX_SILENT_TURNS) get().stop(PAUSED);
      else listen();
    };
    recognition = instance;
    set({ status: "listening", hearing: "" });
    try {
      instance.start();
    } catch {
      get().stop(BLOCKED);
    }
  }

  async function answer(text: string) {
    set({ status: "thinking", hearing: "" });
    const reply = await useChatStore.getState().send(text, "voice");
    if (!active) return;
    speak(reply?.text ?? "No answer came back for this question.");
  }

  function speak(text: string) {
    const synth = synthesis();
    if (!active || !synth) return;
    set({ status: "speaking" });
    synth.cancel();
    const parts = chunks(speakable(text));
    const voice = pickVoice(synth);
    parts.forEach((part, index) => {
      const utterance = new SpeechSynthesisUtterance(part);
      utterance.lang = VOICE_LANG;
      if (voice) utterance.voice = voice;
      if (index === parts.length - 1) {
        utterance.onend = () => listen();
        utterance.onerror = () => listen();
      }
      synth.speak(utterance);
    });
    if (!parts.length) listen();
  }

  return {
    status: "idle",
    hearing: "",
    notice: null,

    start: () => {
      if (active) return;
      if (!voiceChatSupported()) {
        set({ notice: UNSUPPORTED });
        return;
      }
      active = true;
      silentTurns = 0;
      set({ notice: null });
      useChatStore.getState().setOpen(true);
      listen();
    },

    stop: (notice = null) => {
      active = false;
      const current = recognition;
      recognition = null;
      current?.abort();
      synthesis()?.cancel();
      set({ status: "idle", hearing: "", notice });
    },
  };
});
