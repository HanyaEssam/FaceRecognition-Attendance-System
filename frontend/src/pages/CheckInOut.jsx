import { useRef, useState } from "react";
import WebcamCapture from "../components/WebcamCapture";
import { checkIn } from "../api";

function CheckInOut() {
  const camRef = useRef(null);
  const fileInputRef = useRef(null);
  const [action, setAction] = useState("check_in");
  const [response, setResponse] = useState(null);
  const [busy, setBusy] = useState(false);
  const [showDebug, setShowDebug] = useState(false);

  const submitImage = async (image) => {
    setBusy(true);
    setResponse(null);
    try {
      const camera = action === "check_in" ? "main gate in" : "main gate out";
      const data = await checkIn({ image, action, camera });
      setResponse(data);
    } catch (err) {
      setResponse({ faces_detected: 0, results: [
        { result: "error", message: err.response?.data?.detail || err.message }
      ]});
    } finally {
      setBusy(false);
    }
  };

  const handleCapture = async () => {
    const image = camRef.current?.capture();
    if (!image) return;
    submitImage(image);
  };

  const handleFileButtonClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => submitImage(reader.result);
    reader.onerror = () => {
      setResponse({ faces_detected: 0, results: [
        { result: "error", message: "Could not read the selected image file." }
      ]});
    };
    reader.readAsDataURL(file);
    e.target.value = ""; // allow re-selecting the same file later
  };

  const alertClass = (r) => {
    if (r.result === "check_in") return r.status === "on_time" ? "alert-success" : "alert-warning";
    if (r.result === "check_out") return "alert-success";
    if (r.result === "visitor_check_in") return "alert-info";
    if (r.result === "visitor_check_out") return "alert-success";
    if (r.result === "visitor_already_checked_in") return "alert-info";
    if (r.result === "visitor_no_session") return "alert-warning";
    if (r.result === "no_face") return "alert-warning";
    return "alert-danger";
  };

  const messageFor = (r) => {
    if (r.message) return r.message;
    if (r.result === "check_in") return `${r.employee_name} checked in — ${r.status}`;
    if (r.result === "check_out") return `${r.employee_name} checked out`;
    return "Unrecognized result.";
  };

  return (
    <div className="checkin-layout">
      <div>
        <WebcamCapture ref={camRef} />
        <div className="action-row">
          <label>
            <input type="radio" name="action" checked={action === "check_in"}
                   onChange={() => setAction("check_in")} /> Check In
          </label>
          <label>
            <input type="radio" name="action" checked={action === "check_out"}
                   onChange={() => setAction("check_out")} /> Check Out
          </label>
        </div>
        <div className="action-row">
          <button className="btn-primary" onClick={handleCapture} disabled={busy}>
            {busy ? "Processing…" : "Capture & Submit"}
          </button>
          <button className="btn-secondary" onClick={handleFileButtonClick} disabled={busy}>
            Upload Image
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            style={{ display: "none" }}
            onChange={handleFileChange}
          />
        </div>
        <p className="hint">
          A single photo can include more than one person — everyone detected in frame
          is checked in or out individually.
        </p>
      </div>

      <div>
        {response && (
          <>
            {response.faces_detected > 1 && (
              <p className="hint">{response.faces_detected} people detected in this photo.</p>
            )}
            {response.results.map((r, i) => (
              <div key={i} className={`alert ${alertClass(r)}`}>
                {response.faces_detected > 1 && <strong>Person {i + 1}: </strong>}
                {messageFor(r)}
              </div>
            ))}

            {response.results.some((r) => r.liveness_details) && (
              <div className="debug-box">
                <div className="debug-box-header">
                  <strong>Liveness debug</strong>
                  <button className="btn-link" onClick={() => setShowDebug((v) => !v)}>
                    {showDebug ? "hide" : "show"}
                  </button>
                </div>
                {showDebug && response.results.map((r, i) => (
                  r.liveness_details ? (
                    <pre key={i}>{JSON.stringify(r.liveness_details, null, 2)}</pre>
                  ) : null
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default CheckInOut;