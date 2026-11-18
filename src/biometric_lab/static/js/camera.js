// Webcam capture. Produces a base64 JPEG frame. The camera light is on only while a
// stream is active; stop() releases it. Decoding JPEG server-side needs the real engine
// extra (opencv); with the fake engine, captures return FTA (expected).
class CameraController {
  constructor(videoEl) {
    this.video = videoEl;
    this.stream = null;
  }
  async start() {
    this.stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640 } });
    this.video.srcObject = this.stream;
    await this.video.play();
  }
  stop() {
    if (this.stream) {
      this.stream.getTracks().forEach((t) => t.stop());
      this.stream = null;
      this.video.srcObject = null;
    }
  }
  capture() {
    const w = 640;
    const h = this.video.videoHeight && this.video.videoWidth
      ? Math.round((this.video.videoHeight / this.video.videoWidth) * w)
      : 480;
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    canvas.getContext("2d").drawImage(this.video, 0, 0, w, h);
    return canvas.toDataURL("image/jpeg", 0.9).split(",")[1];
  }
}

// Release cameras when the page is hidden (privacy).
document.addEventListener("visibilitychange", () => {
  if (document.hidden && window.__cameras) {
    window.__cameras.forEach((c) => c.stop());
  }
});
