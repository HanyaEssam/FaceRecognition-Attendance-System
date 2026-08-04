import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";

const WebcamCapture = forwardRef(function WebcamCapture(
  {
    width = 640,
    height = 480,
    quality = 0.75,
    onReady,
    onError,
  },
  ref
) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);

  // Store callback functions in refs so callback changes do not restart
  // the physical camera stream.
  const onReadyRef = useRef(onReady);
  const onErrorRef = useRef(onError);

  const [ready, setReady] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    onReadyRef.current = onReady;
  }, [onReady]);

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  useEffect(() => {
    let cancelled = false;

    const startCamera = async () => {
      try {
        setReady(false);
        setErrorMessage("");

        if (!navigator.mediaDevices?.getUserMedia) {
          throw new Error(
            "Camera access requires HTTPS or localhost."
          );
        }

        const stream = await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: {
            width: { ideal: width },
            height: { ideal: height },
            facingMode: "user",
          },
        });

        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }

        streamRef.current = stream;

        const video = videoRef.current;

        if (video) {
          video.srcObject = stream;

          // Wait until video metadata is available.
          await new Promise((resolve) => {
            if (video.readyState >= 1) {
              resolve();
              return;
            }

            video.onloadedmetadata = () => resolve();
          });

          await video.play();
        }

        if (!cancelled) {
          setReady(true);
          onReadyRef.current?.();
        }
      } catch (error) {
        if (cancelled) {
          return;
        }

        console.error("Camera error:", error);

        let message =
          error.message || "Could not open the camera.";

        if (error.name === "NotAllowedError") {
          message =
            "Camera permission was denied. Allow camera access from the browser address bar.";
        } else if (error.name === "NotFoundError") {
          message = "No camera was found.";
        } else if (error.name === "NotReadableError") {
          message =
            "The camera is already being used by another application or browser tab.";
        }

        setErrorMessage(message);
        setReady(false);
        onErrorRef.current?.(error);
      }
    };

    startCamera();

    return () => {
      cancelled = true;

      if (streamRef.current) {
        streamRef.current
          .getTracks()
          .forEach((track) => track.stop());

        streamRef.current = null;
      }
    };
  }, [width, height]);

  useImperativeHandle(
    ref,
    () => ({
      capture() {
        const video = videoRef.current;
        const canvas = canvasRef.current;

        if (
          !ready ||
          !video ||
          !canvas ||
          video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA
        ) {
          return null;
        }

        const captureWidth = video.videoWidth || width;
        const captureHeight = video.videoHeight || height;

        canvas.width = captureWidth;
        canvas.height = captureHeight;

        const context = canvas.getContext("2d");

        if (!context) {
          return null;
        }

        context.drawImage(
          video,
          0,
          0,
          captureWidth,
          captureHeight
        );

        return canvas.toDataURL("image/jpeg", quality);
      },

      isReady() {
        return ready;
      },

      stop() {
        if (streamRef.current) {
          streamRef.current
            .getTracks()
            .forEach((track) => track.stop());

          streamRef.current = null;
          setReady(false);
        }
      },
    }),
    [ready, width, height, quality]
  );

  return (
    <div className="webcam-container">
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className="webcam-video"
        style={{ transform: "scaleX(-1)" }}
      />

      <canvas
        ref={canvasRef}
        style={{ display: "none" }}
      />

      {!ready && !errorMessage && (
        <div className="camera-overlay">
          Starting camera...
        </div>
      )}

      {errorMessage && (
        <div className="alert alert-danger">
          {errorMessage}
        </div>
      )}
    </div>
  );
});

export default WebcamCapture;