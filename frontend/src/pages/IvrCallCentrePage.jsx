import { useEffect, useState } from "react";
import {
  Phone,
  PhoneCall,
  Loader2,
  CheckCircle,
  Globe,
  MessageSquare,
} from "lucide-react";

import { api } from "../api/client";
import { ErrorAlert } from "../components/Ui";

export default function IvrCallCenterPage() {
  const [phoneNumber, setPhoneNumber] = useState("");
  const [language, setLanguage] = useState("en");
  const [purpose, setPurpose] = useState("general");
  const [outboundStatus, setOutboundStatus] = useState(null);
  const [statusLoading, setStatusLoading] = useState(true);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [callResult, setCallResult] = useState(null);

  useEffect(() => {
    let active = true;

    async function loadOutboundStatus() {
      try {
        const response = await api.ivrOutboundStatus();
        if (!active) return;
        setOutboundStatus(response);
      } catch (err) {
        if (!active) return;
        setError(err.message || "Unable to verify Twilio outbound setup");
      } finally {
        if (active) setStatusLoading(false);
      }
    }

    loadOutboundStatus();

    return () => {
      active = false;
    };
  }, []);

  async function startCall() {
    setLoading(true);
    setError("");
    setCallResult(null);

    try {
      const response = await api.startIvrCall(phoneNumber, language, purpose);

      setCallResult(response);
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          err.message ||
          "Unable to place call"
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <header className="page-header">
        <span className="eyebrow">IVR Operations</span>
        <h2>Outbound Farmer Call</h2>
        <p>
          Start a real IVR call using Twilio and KrishiMitra Voice AI.
        </p>
      </header>

      <ErrorAlert error={error} />

      <div className="panel">
        <h3>Twilio Outbound Setup</h3>
        <p>
          {statusLoading
            ? "Checking your Twilio caller ID and public webhook URL..."
            : outboundStatus?.message || "Twilio outbound status is unavailable."}
        </p>

        {outboundStatus && (
          <div className="call-details">
            <div>
              <strong>Status</strong>
              <p>{outboundStatus.ready ? "Ready" : "Action needed"}</p>
            </div>

            <div>
              <strong>Caller ID</strong>
              <p>{outboundStatus.from_number || "Not configured"}</p>
            </div>

            <div>
              <strong>Validation</strong>
              <p>{outboundStatus.validated_source || "Not verified"}</p>
            </div>

            <div>
              <strong>Webhook</strong>
              <p>{outboundStatus.webhook_url || "Unavailable"}</p>
            </div>
          </div>
        )}
      </div>

      <div className="panel">
        <div className="form-grid">
          <label>
            <span>Farmer Phone Number</span>

            <div className="input-with-icon">
              <Phone size={18} />

              <input
                type="tel"
                placeholder="+919876543210"
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value)}
              />
            </div>
          </label>

          <label>
            <span>Language</span>

            <div className="input-with-icon">
              <Globe size={18} />

              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
              >
                <option value="en">English</option>
                <option value="ta">Tamil</option>
                <option value="kn">Kannada</option>
              </select>
            </div>
          </label>

          <label>
            <span>Call Purpose</span>

            <div className="input-with-icon">
              <MessageSquare size={18} />

              <select
                value={purpose}
                onChange={(e) => setPurpose(e.target.value)}
              >
                <option value="general">General Assistance</option>
                <option value="weather">Weather Advisory</option>
                <option value="crop">Crop Support</option>
                <option value="scheme">Government Schemes</option>
                <option value="grievance">Grievance Support</option>
              </select>
            </div>
          </label>
        </div>

        <button
          className="primary-button"
          onClick={startCall}
          disabled={loading || statusLoading || !outboundStatus?.ready || !phoneNumber}
        >
          {loading ? (
            <>
              <Loader2 size={18} className="spin" />
              Initiating Call...
            </>
          ) : (
            <>
              <PhoneCall size={18} />
              Start IVR Call
            </>
          )}
        </button>
      </div>

      {callResult && (
        <div className="panel success-panel">
          <div className="success-header">
            <CheckCircle size={24} />
            <h3>Call Initiated Successfully</h3>
          </div>

          <div className="call-details">
            <div>
              <strong>Call SID</strong>
              <p>{callResult.call_sid}</p>
            </div>

            <div>
              <strong>Status</strong>
              <p>{callResult.status}</p>
            </div>

            <div>
              <strong>Phone</strong>
              <p>{phoneNumber}</p>
            </div>

            <div>
              <strong>Language</strong>
              <p>{language.toUpperCase()}</p>
            </div>

            <div>
              <strong>Purpose</strong>
              <p>{purpose}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
