import { useRef, useEffect, useState, useImperativeHandle, forwardRef } from "react";

// Reusable webcam preview + capture component. Exposes a `capture()`
// method via ref that returns a base64 JPEG data URL of the current frame.
const WebcamCapture = forwardRef(function WebcamCapture(_props, ref) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const [error, setError] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let stream;
    navigator.mediaDevices
      .getUserMedia({ video: { width: 640, height: 480 } })
      .then((s) => {
        stream = s;
        if (videoRef.current) {
          videoRef.current.srcObject = s;
          setReady(true);
        }
      })
      .catch((err) => setError(err.message));

    return () => {
      if (stream) stream.getTracks().forEach((t) => t.stop());
    };
  }, []);

  useImperativeHandle(ref, () => ({
    capture() {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas) return null;
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      return canvas.toDataURL("image/jpeg", 0.9);
    },
  }));

  if (error) {
    return <div className="alert alert-danger">Could not access webcam: {error}</div>;
  }

  return (
    <div className="webcam-frame">
      <div className="webcam-wrap">
        <video ref={videoRef} autoPlay playsInline muted className="webcam-video" style={{transform: "scaleX(-1)"}}/>
        <canvas ref={canvasRef} style={{ display: "none" }} />
        {!ready && <p style={{ color: "#C7CDD8", padding: "12px 14px", margin: 0 }}>Requesting camera access…</p>}
      </div>
      <span className="scan-corner tl" />
      <span className="scan-corner tr" />
      <span className="scan-corner bl" />
      <span className="scan-corner br" />
    </div>
  );
});

export default WebcamCapture;
