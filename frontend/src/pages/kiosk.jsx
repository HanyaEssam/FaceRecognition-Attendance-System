import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import { useOutletContext } from "react-router-dom";

import WebcamCapture from "../components/WebcamCapture";
import { kioskScan } from "../api";

const SCAN_INTERVAL_MS = 4000;

const RESULT_LABELS = {
  check_in: (result) =>
    `${result.employee_name} checked in — ${result.status}`,

  check_out: (result) =>
    `${result.employee_name} checked out`,

  no_check_in: (result) =>
    `${result.employee_name} has not checked in today`,

  already_done: (result) =>
    `${result.employee_name} already checked out today`,

  too_soon: (result) =>
    `${result.employee_name} is already checked in`,

  cooldown: () =>
    "Person was recently processed",

  visitor_check_in: () =>
    "Visitor checked in",

  visitor_check_out: (result) =>
    `Visitor checked out after ${result.duration_minutes} minutes`,

  visitor_too_soon: () =>
    "Visitor is already checked in",

  visitor_no_session: () =>
    "No matching visitor check-in was found",

  spoof_suspected: (result) =>
    result.message || "Liveness check failed",

  processing_error: (result) =>
    result.message || "Face processing failed",
};

const RESULT_TONES = {
  check_in: "alert-success",
  check_out: "alert-success",

  visitor_check_in: "alert-info",
  visitor_check_out: "alert-success",

  no_check_in: "alert-danger",
  already_done: "alert-info",
  too_soon: "alert-info",
  cooldown: "alert-info",
  visitor_too_soon: "alert-info",
  visitor_no_session: "alert-danger",

  spoof_suspected: "alert-danger",
  processing_error: "alert-danger",
};

function Kiosk() {
  const { selectedCamera } = useOutletContext();

  const cameraRef = useRef(null);
  const timeoutRef = useRef(null);
  const requestRunningRef = useRef(false);

  const [cameraReady, setCameraReady] =
    useState(false);

  const [facesDetected, setFacesDetected] =
    useState(0);

  const [events, setEvents] = useState([]);
  const [error, setError] = useState("");
  const [lastScanTime, setLastScanTime] =
    useState(null);

  const addEvents = useCallback((results) => {
    const hiddenResults = new Set([
      "cooldown",
      "too_soon",
    ]);

    const meaningfulResults = results.filter(
      (result) =>
        !hiddenResults.has(result.result)
    );

    if (meaningfulResults.length === 0) {
      return;
    }

    const newEvents = meaningfulResults.map(
      (result) => {
        const createLabel =
          RESULT_LABELS[result.result] ||
          (() =>
            result.message ||
            result.result ||
            "Unknown result");

        return {
          id: `${Date.now()}-${Math.random()}`,
          time: new Date().toLocaleTimeString(),
          text: createLabel(result),
          tone:
            RESULT_TONES[result.result] ||
            "alert-info",
        };
      }
    );

    setEvents((previousEvents) =>
      [...newEvents, ...previousEvents].slice(
        0,
        30
      )
    );
  }, []);

  const handleCameraReady = useCallback(() => {
    setCameraReady(true);
    setError("");
  }, []);

  const handleCameraError = useCallback(
    (cameraError) => {
      setCameraReady(false);

      setError(
        cameraError?.message ||
          "Could not access the camera."
      );
    },
    []
  );

  useEffect(() => {
    if (!cameraReady || !selectedCamera) {
      return undefined;
    }

    let cancelled = false;

    const scheduleNextScan = (
      delay = SCAN_INTERVAL_MS
    ) => {
      if (cancelled) {
        return;
      }

      timeoutRef.current = window.setTimeout(
        scanFrame,
        delay
      );
    };

    const scanFrame = async () => {
      if (
        cancelled ||
        requestRunningRef.current
      ) {
        scheduleNextScan();
        return;
      }

      if (
        document.visibilityState !== "visible"
      ) {
        scheduleNextScan();
        return;
      }

      const image =
        cameraRef.current?.capture();

      if (!image) {
        scheduleNextScan(1000);
        return;
      }

      requestRunningRef.current = true;

      try {
        const response = await kioskScan({
          image,

          // main gate in or main gate out
          camera: selectedCamera.name,

          // in or out
          direction: selectedCamera.direction,
        });

        if (cancelled) {
          return;
        }

        setError("");

        setFacesDetected(
          response.faces_detected ?? 0
        );

        setLastScanTime(new Date());

        if (Array.isArray(response.results)) {
          addEvents(response.results);
        }
      } catch (requestError) {
        if (cancelled) {
          return;
        }

        console.error(
          "Kiosk scan failed:",
          requestError
        );

        const message =
          requestError.response?.data?.detail ||
          requestError.response?.data?.message ||
          requestError.message ||
          "Could not connect to the backend.";

        setError(message);
      } finally {
        requestRunningRef.current = false;

        if (!cancelled) {
          scheduleNextScan();
        }
      }
    };

    // Start a new scan shortly after switching cameras.
    scheduleNextScan(700);

    return () => {
      cancelled = true;
      requestRunningRef.current = false;

      if (timeoutRef.current) {
        window.clearTimeout(
          timeoutRef.current
        );
      }
    };
  }, [
    cameraReady,
    selectedCamera,
    addEvents,
  ]);

  return (
    <div className="checkin-layout">
      <section>
        <h2>Kiosk Mode</h2>

        <WebcamCapture
          ref={cameraRef}
          onReady={handleCameraReady}
          onError={handleCameraError}
        />

        <div className="kiosk-status-card">
          <p>
            Camera:{" "}
            <strong>
              {selectedCamera.name}
            </strong>
          </p>

          <p>
            Action:{" "}
            <strong>
              {selectedCamera.direction === "in"
                ? "Check In"
                : "Check Out"}
            </strong>
          </p>

          <p>
            Status:{" "}
            <strong>
              {cameraReady
                ? "Watching continuously"
                : "Waiting for camera"}
            </strong>
          </p>

          <p>
            Faces in last frame:{" "}
            <strong>{facesDetected}</strong>
          </p>

          {lastScanTime && (
            <p>
              Last scan:{" "}
              <strong>
                {lastScanTime.toLocaleTimeString()}
              </strong>
            </p>
          )}
        </div>

        {error && (
          <div className="alert alert-danger">
            <strong>Error:</strong> {error}
          </div>
        )}

        <p className="hint">
          When main gate in is selected,
          recognized employees are checked in.
          When main gate out is selected,
          recognized employees are checked out.
        </p>
      </section>

      <section>
        <div className="activity-heading">
          <h3>Recent activity</h3>

          {events.length > 0 && (
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setEvents([])}
            >
              Clear
            </button>
          )}
        </div>

        {events.length === 0 && (
          <p className="hint">
            No attendance events detected yet.
          </p>
        )}

        {events.map((event) => (
          <div
            key={event.id}
            className={`alert ${event.tone}`}
          >
            <span
              className="hint"
              style={{ marginRight: 8 }}
            >
              {event.time}
            </span>

            {event.text}
          </div>
        ))}
      </section>
    </div>
  );
}

export default Kiosk;
