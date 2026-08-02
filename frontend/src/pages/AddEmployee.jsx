import { useRef, useState } from "react";
import WebcamCapture from "../components/WebcamCapture";
import { createEmployee } from "../api";
import { Info, Camera, RotateCcw, Save } from "lucide-react";

const NUM_CAPTURES_NEEDED = 3;

function AddEmployee() {
  const camRef = useRef(null);
  const [form, setForm] = useState({
    name: "", department: "", shift_start: "09:00", shift_end: "17:00",
    national_id: "", job_title: "", gender: "", marital_status: "", birth_date: "", address: "",
  });
  const [captures, setCaptures] = useState([]);
  const [message, setMessage] = useState(null);
  const [busy, setBusy] = useState(false);

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  const captureOne = () => {
    const image = camRef.current?.capture();
    if (!image) return;
    if (captures.length < NUM_CAPTURES_NEEDED) {
      setCaptures([...captures, image]);
      setMessage(`Captured photo ${captures.length + 1} of ${NUM_CAPTURES_NEEDED}.`);
    }
  };

  const reset = () => { setCaptures([]); setMessage(null); };

  const save = async () => {
    if (!form.name.trim()) { setMessage("Please enter a name before saving."); return; }
    setBusy(true);
    try {
      const payload = { ...form, images: captures };
      const data = await createEmployee(payload);
      setMessage(`'${form.name}' enrolled successfully (${data.captures_used} usable captures).`);
      setCaptures([]);
      setForm({ name: "", department: "", shift_start: "09:00",shift_end: "17:00", national_id: "", job_title: "",
                gender: "", marital_status: "", birth_date: "", address: "" });
    } catch (err) {
      setMessage(err.response?.data?.detail || err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <p className="hint">
        <Info size={15} />
        Fill in their details, then capture a few photos from different angles.
        The system averages the captures into one profile — no training involved.
      </p>

      <div className="profile-grid">
        <label>Full name <input value={form.name} onChange={set("name")} /></label>
        <label>Department <input value={form.department} onChange={set("department")} /></label>
        <label>Shift start (HH:MM) <input value={form.shift_start} onChange={set("shift_start")} /></label>
        <label>Shift end (HH:MM) <input value={form.shift_end} onChange={set("shift_end")} /></label>
      </div>

      <details>
        <summary>Additional profile details (optional — may later sync from HR system)</summary>
        <div className="profile-grid">
          <label>National ID <input value={form.national_id} onChange={set("national_id")} /></label>
          <label>Job Title <input value={form.job_title} onChange={set("job_title")} /></label>
          <label>Gender
            <select value={form.gender} onChange={set("gender")}>
              <option value="">—</option><option value="Male">Male</option><option value="Female">Female</option>
            </select>
          </label>
          <label>Marital Status <input value={form.marital_status} onChange={set("marital_status")} /></label>
          <label>Birth Date <input value={form.birth_date} onChange={set("birth_date")} placeholder="YYYY-MM-DD" /></label>
          <label>Address <input value={form.address} onChange={set("address")} /></label>
        </div>
      </details>

      <p>Captures so far: <strong>{captures.length} / {NUM_CAPTURES_NEEDED}</strong></p>

      <WebcamCapture ref={camRef} />
      <div className="action-row">
        <button className="btn-primary" onClick={captureOne} disabled={captures.length >= NUM_CAPTURES_NEEDED}>
          <Camera size={16} /> Capture photo
        </button>
        <button className="btn-secondary" onClick={reset}>
          <RotateCcw size={16} /> Reset captures
        </button>
      </div>

      {captures.length >= NUM_CAPTURES_NEEDED && (
        <button className="btn-primary" onClick={save} disabled={busy}>
          <Save size={16} /> {busy ? "Saving…" : "Save employee"}
        </button>
      )}

      {message && <div className="alert alert-info" style={{ marginTop: 12 }}>{message}</div>}
    </div>
  );
}

export default AddEmployee;
