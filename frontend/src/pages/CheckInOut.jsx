import { useRef, useState } from "react";
import WebcamCapture from "../components/WebcamCapture";
import { checkIn } from "../api";

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
      const camera = action === "check_in" ? "main gate in" : "main gate out";
      const data = await checkIn({ image, action, camera });
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
    if (r.result === "visitor_check_in") return "alert-info";
    if (r.result === "visitor_check_out") return "alert-success";
    if (r.result === "visitor_already_checked_in") return "alert-info";
    if (r.result === "visitor_no_session") return "alert-warning";
    if (r.result === "no_face") return "alert-warning";
    return "alert-danger";
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
        <button className="btn-primary" onClick={handleCapture} disabled={busy}>
          {busy ? "Processing…" : "Capture & Submit"}
        </button>
      </div>

      <div>
        {result && (
          <div className={`alert ${alertClass(result)}`}>
            {result.message ||
              (result.result === "check_in" && `${result.employee_name} checked in — ${result.status}`) ||
              (result.result === "check_out" && `${result.employee_name} checked out`)}
          </div>
        )}

        {result?.liveness_details && showDebug && (
          <div className="debug-box">
            <div className="debug-box-header">
              <strong>Liveness debug</strong>
              <button className="btn-link" onClick={() => setShowDebug(false)}>hide</button>
            </div>
            <pre>{JSON.stringify(result.liveness_details, null, 2)}</pre>
          </div>
        )}
      </div>
    </div>
  );
}

export default CheckInOut;