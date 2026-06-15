import { useState } from "react";
import { api } from "../api/client";
import { ErrorAlert } from "../components/Ui";

export default function VoicePage() {
  const [audio, setAudio] = useState(null);
  const [transcript, setTranscript] = useState(null);
  const [speakText, setSpeakText] = useState("");
  const [language, setLanguage] = useState("ta-IN");
  const [audioUrl, setAudioUrl] = useState("");
  const [error, setError] = useState("");

  async function transcribe(event) {
    event.preventDefault();
    if (!audio) return;
    setError("");
    setTranscript(null);
    try {
      const formData = new FormData();
      formData.append("audio", audio);
      formData.append("language", language);
      setTranscript(await api.transcribeVoice(formData));
    } catch (err) {
      setError(err.message);
    }
  }

  async function speak(event) {
    event.preventDefault();
    setError("");
    setAudioUrl("");
    try {
      const blob = await api.speak({ text: speakText, language });
      setAudioUrl(URL.createObjectURL(blob));
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="page">
      <header className="page-header"><h2>Voice Assistant</h2><p>Convert farmer speech to text and generate spoken responses.</p></header>
      <ErrorAlert error={error} />
      <div className="two-column">
        <section className="panel">
          <h3>Speech to text</h3>
          <form className="form-stack" onSubmit={transcribe}>
            <label>Language<select value={language} onChange={(e) => setLanguage(e.target.value)}><option value="ta-IN">Tamil</option><option value="hi-IN">Hindi</option><option value="kn-IN">Kannada</option><option value="en-IN">English</option></select></label>
            <label>Audio file<input type="file" accept="audio/*" onChange={(e) => setAudio(e.target.files?.[0])} required /></label>
            <button className="primary-button">Transcribe</button>
          </form>
          {transcript && <div className="result-list"><strong>Transcript</strong><p>{transcript.transcript}</p><span>{transcript.language}</span></div>}
        </section>
        <section className="panel">
          <h3>Text to speech</h3>
          <form className="form-stack" onSubmit={speak}>
            <label>Text<textarea rows="6" maxLength="1000" required value={speakText} onChange={(e) => setSpeakText(e.target.value)} /></label>
            <button className="primary-button">Generate audio</button>
          </form>
          {audioUrl && <audio className="audio-player" controls src={audioUrl} />}
        </section>
      </div>
    </div>
  );
}

