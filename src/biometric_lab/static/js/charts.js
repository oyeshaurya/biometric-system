// Tiny canvas plot for FAR/FRR vs threshold with operating-point and EER markers.
// No external dependency, so the page stays self-contained and CSP-strict.
function drawSweep(canvas, data) {
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  const pad = { l: 46, r: 12, t: 14, b: 34 };
  const plotW = W - pad.l - pad.r, plotH = H - pad.t - pad.b;

  const thr = data.curve.thresholds, far = data.curve.far, frr = data.curve.frr;
  if (!thr.length) {
    ctx.fillStyle = "#5b6b7b";
    ctx.fillText("No decided trials to plot.", pad.l, pad.t + 20);
    return;
  }
  const xmin = Math.min(...thr), xmax = Math.max(...thr);
  const sx = (x) => pad.l + ((x - xmin) / (xmax - xmin || 1)) * plotW;
  const sy = (y) => pad.t + (1 - y) * plotH;

  // axes
  ctx.strokeStyle = "#d9e1ea"; ctx.lineWidth = 1;
  ctx.strokeRect(pad.l, pad.t, plotW, plotH);
  ctx.fillStyle = "#5b6b7b"; ctx.font = "11px system-ui";
  for (let g = 0; g <= 1.0001; g += 0.25) {
    const y = sy(g);
    ctx.strokeStyle = "#eef2f7";
    ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(pad.l + plotW, y); ctx.stroke();
    ctx.fillText(g.toFixed(2), 6, y + 3);
  }
  ctx.fillText("threshold", pad.l + plotW / 2 - 24, H - 8);

  const line = (arr, color) => {
    ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.beginPath();
    arr.forEach((v, i) => {
      const x = sx(thr[i]), y = sy(v);
      i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    });
    ctx.stroke();
  };
  line(far, "#c0392b");
  line(frr, "#1f5fbf");

  // operating threshold marker
  if (data.operating_threshold != null && data.operating_threshold >= xmin && data.operating_threshold <= xmax) {
    const x = sx(data.operating_threshold);
    ctx.strokeStyle = "#0f8a8a"; ctx.setLineDash([4, 3]);
    ctx.beginPath(); ctx.moveTo(x, pad.t); ctx.lineTo(x, pad.t + plotH); ctx.stroke();
    ctx.setLineDash([]);
  }
  // EER marker
  const eer = data.eer && data.eer.interpolated;
  if (eer) {
    const x = sx(eer.threshold), y = sy(eer.value);
    ctx.fillStyle = "#8a5a0f";
    ctx.beginPath(); ctx.arc(x, y, 4, 0, 2 * Math.PI); ctx.fill();
  }

  // legend
  ctx.fillStyle = "#c0392b"; ctx.fillText("FAR", pad.l + 8, pad.t + 12);
  ctx.fillStyle = "#1f5fbf"; ctx.fillText("FRR", pad.l + 40, pad.t + 12);
  ctx.fillStyle = "#0f8a8a"; ctx.fillText("op", pad.l + 72, pad.t + 12);
  ctx.fillStyle = "#8a5a0f"; ctx.fillText("EER", pad.l + 96, pad.t + 12);
}
