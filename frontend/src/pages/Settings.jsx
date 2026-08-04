import { Info } from "lucide-react";

function Settings() {
  return (
    <div>
      <p className="hint">
        <Info size={15} />
        Placeholder page — camera assignment, thresholds, and integration settings will live here.
      </p>
      <p>Liveness detection thresholds are configured server-side in <code>face_pipeline.py</code>.</p>
    </div>
  );
}

export default Settings;
