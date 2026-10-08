import { describe, expect, it } from "vitest";
import { chunks, speakable, speakLine } from "./speakable";

// The answers' shapes, as the risk engine writes them.
const RANKING = [
  "Indicators suggest HIGH or CRITICAL risk in 1 of 7 monitored areas:",
  "#1 Jiribam farmland near Kamaranga: HIGH, 71/100 (confidence low)",
  "Moderate: 4, low: 2, not enough data: 0 of 7 monitored areas.",
  "PLACEHOLDER thresholds: prototype scores, not validated agricultural findings.",
  "Pest-report figures are SAMPLE DATA — Prototype Simulation.",
].join("\n");
const EXPLANATION = [
  "Bishnupur farmland near Keinou Thongkha (Nambol): LOW, 29/100 (confidence low). Rank #6 of 7.",
  "Why:",
  "- 7 SAMPLE pest report(s) in the last 14 days (brown planthopper x4, rice blast x3).",
  "- Rice blast: favourable on 0 of the last 7 days (at least 11 h with relative humidity >= 95%; daily mean temperature 22-28 °C). [PLACEHOLDER thresholds, not yet verified]",
  "- Brown planthopper: favourable on 0 of the last 7 days.",
  "- Vegetation condition (NDVI) is unavailable.",
  "PLACEHOLDER thresholds: prototype scores, not validated agricultural findings.",
].join("\n");

describe("speaking an answer", () => {
  it("reads scores, ranks and confidence aloud without changing them", () => {
    const spoken = speakable(RANKING);
    expect(spoken).toContain("number 1 Jiribam farmland near Kamaranga: HIGH, 71 out of 100 (confidence low)");
    expect(spoken).toContain("1 of 7 monitored areas");
    expect(spoken).toContain("Moderate: 4, low: 2, not enough data: 0 of 7");
  });

  it("keeps every PLACEHOLDER and SAMPLE warning", () => {
    const spoken = speakable(RANKING);
    expect(spoken).toContain("PLACEHOLDER thresholds: prototype scores, not validated agricultural findings.");
    expect(spoken).toContain("SAMPLE DATA, Prototype Simulation");
  });

  it("reads the first reasons and points to the screen for the rest", () => {
    const spoken = speakable(EXPLANATION);
    expect(spoken).toContain("7 SAMPLE pest report(s)");
    expect(spoken).toContain("at least 11 hours with relative humidity at least 95%");
    expect(spoken).toContain("22-28 degrees Celsius");
    expect(spoken).toContain("PLACEHOLDER thresholds, not yet verified");
    expect(spoken).not.toContain("Brown planthopper: favourable");
    expect(spoken).toContain("2 more reasons are shown on screen.");
    expect(spoken).toContain("29 out of 100");
    expect(spoken.endsWith("2 more reasons are shown on screen.")).toBe(false); // the closing warning still comes
  });

  it("speaks numbered inspection lines as numbers", () => {
    expect(speakLine("1. Jiribam farmland: HIGH, 71/100")).toBe("Number 1, Jiribam farmland: HIGH, 71 out of 100.");
  });
});

describe("splitting speech into utterances", () => {
  it("keeps sentences whole and decimals intact", () => {
    const parts = chunks("Mean NDVI 0.62. ".repeat(30), 100);
    expect(parts.length).toBeGreaterThan(1);
    expect(parts.every((p) => p.length <= 100)).toBe(true);
    expect(parts.join(" ")).toContain("0.62");
  });
});
