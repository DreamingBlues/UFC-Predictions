"use client";

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function FighterPicker({ label, value, onChange, disabledName }) {
  const [suggestions, setSuggestions] = useState([]);
  const [selectedName, setSelectedName] = useState("");

  useEffect(() => {
    const query = value.trim();
    if (!query || query === selectedName) {
      setSuggestions([]);
      return undefined;
    }

    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const response = await fetch(
          `${API_URL}/fighters/search?q=${encodeURIComponent(query)}`,
          { signal: controller.signal }
        );
        if (response.ok) {
          const data = await response.json();
          setSuggestions(data.fighters || []);
        }
      } catch (error) {
        if (error.name !== "AbortError") setSuggestions([]);
      }
    }, 180);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [value, selectedName]);

  const filteredSuggestions = suggestions.filter(
    (name) => name !== disabledName
  );

  return (
    <label className="picker">
      <span>{label}</span>
      <input
        value={value}
        onChange={(event) => {
          setSelectedName("");
          onChange(event.target.value);
        }}
        placeholder="Search a fighter"
        autoComplete="off"
      />
      {filteredSuggestions.length > 0 && (
        <div className="suggestions">
          {filteredSuggestions.map((name) => (
            <button
              type="button"
              key={name}
              onClick={() => {
                setSelectedName(name);
                onChange(name);
                setSuggestions([]);
              }}
            >
              {name}
            </button>
          ))}
        </div>
      )}
    </label>
  );
}

export default function Home() {
  const [fighterA, setFighterA] = useState("");
  const [fighterB, setFighterB] = useState("");
  const [titleBout, setTitleBout] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setResult(null);
    if (!fighterA.trim() || !fighterB.trim()) {
      setError("Choose two fighters first.");
      return;
    }
    if (fighterA.trim().toLowerCase() === fighterB.trim().toLowerCase()) {
      setError("Choose two different fighters.");
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/predictions/winner`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fighter_a: fighterA,
          fighter_b: fighterB,
          title_bout: titleBout
        })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Prediction failed.");
      setResult(data);
    } catch (requestError) {
      setError(requestError.message || "Prediction failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">UFC / WINNER MODEL</p>
        <h1>Who takes the fight?</h1>
        <p className="lede">
          Select two fighters to compare their latest available pre-fight
          snapshots.
        </p>
      </section>

      <form className="card matchup" onSubmit={submit}>
        <div className="pickers">
          <FighterPicker
            label="Fighter A"
            value={fighterA}
            onChange={setFighterA}
            disabledName={fighterB}
          />
          <div className="versus">VS</div>
          <FighterPicker
            label="Fighter B"
            value={fighterB}
            onChange={setFighterB}
            disabledName={fighterA}
          />
        </div>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={titleBout}
            onChange={(event) => setTitleBout(event.target.checked)}
          />
          Title bout
        </label>
        <button className="predict" type="submit" disabled={loading}>
          {loading ? "Running model…" : "Predict winner"}
        </button>
        {error && <p className="error">{error}</p>}
      </form>

      {result && (
        <section className="card result" aria-live="polite">
          <p className="eyebrow">MODEL OUTPUT</p>
          <h2>{result.predicted_winner} is favored</h2>
          <div className="probabilities">
            <div>
              <span>{result.fighter_a}</span>
              <strong>{(result.fighter_a_probability * 100).toFixed(2)}%</strong>
              <div className="bar"><i style={{ width: `${result.fighter_a_probability * 100}%` }} /></div>
            </div>
            <div>
              <span>{result.fighter_b}</span>
              <strong>{(result.fighter_b_probability * 100).toFixed(2)}%</strong>
              <div className="bar"><i style={{ width: `${result.fighter_b_probability * 100}%` }} /></div>
            </div>
          </div>
          <p className="note">
            These are model confidence estimates from <code>predict_proba</code>,
            not calibrated betting probabilities.
          </p>
        </section>
      )}
    </main>
  );
}
