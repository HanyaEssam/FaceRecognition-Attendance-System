import { useRef, useState } from "react";
import WebcamCapture from "../components/WebcamCapture";
import { checkIn } from "../api";
import { Camera, CheckCircle2, AlertTriangle, Info, XCircle } from "lucide-react";

function CheckInOut() {
  const camRef = useRef(null);
  const [action, setAction] = useState("check_in");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [showDebug, setShowDebug] = useState(true);

  const handleCapture = async () => {
    const image = camRef.current?.capture();
    if (!image) return;
    setBusy(true);
    setResult(null);
    try {
      const data = await checkIn({ image, action, camera: "main gate in" });
      setResult(data);
    } catch (err) {
      setResult({ result: "error", message: err.response?.data?.detail || err.message });
    } finally {
      setBusy(false);
    }
  };

  const alertClass = (r) => {
    if (!r) return "";
    if (r.result === "check_in") return r.status === "on_time" ? "alert-success" : "alert-warning";
    if (r.result === "check_out") return "alert-success";
    if (r.result === "visitor") return "alert-info";
    if (r.result === "no_face") return "alert-warning";
    return "alert-danger";
  };

  const alertIcon = (r) => {
    const cls = alertClass(r);
    if (cls === "alert-success") return <CheckCircle2 size={16} />;
    if (cls === "alert-warning") return <AlertTriangle size={16} />;
    if (cls === "alert-info") return <Info size={16} />;
    return <XCircle size={16} />;
  };

  return (
    <div className="checkin-layout">
      <div className="checkin-panel">
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
        <button className="btn-primary" onClick={handleCapture} disabled={busy}>
          <Camera size={16} /> {busy ? "Processing…" : "Capture & Submit"}
        </button>
      </div>

      <div className="checkin-panel">
        {result && (
          <div className={`alert ${alertClass(result)}`}>
            {alertIcon(result)}
            {result.message ||
              (result.result === "check_in" && `${result.employee_name} checked in — ${result.status}`) ||
              (result.result === "check_out" && `${result.employee_name} checked out`)}
          </div>
        )}

        {result?.liveness_details && showDebug && (
          <div className="debug-box">
            <div className="debug-box-header">
              <span>Liveness debug</span>
              <button className="btn-link" onClick={() => setShowDebug(false)}>hide</button>
            </div>
            <pre>{JSON.stringify(result.liveness_details, null, 2)}</pre>
          </div>
        )}

        {!result && (
          <p className="hint" style={{ marginTop: 0 }}>
            <Info size={15} />
            Capture a frame from the camera to check in or out. Results and liveness details appear here.
          </p>
        )}
      </div>
    </div>
  );
}

export default CheckInOut;
