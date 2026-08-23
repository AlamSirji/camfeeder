const RETRY_MS = 5000;
const DISABLED_KEY = "camfeeder:disabled-cams";

function loadDisabledIds() {
  try {
    return new Set(JSON.parse(localStorage.getItem(DISABLED_KEY) || "[]"));
  } catch {
    return new Set();
  }
}

const disabledIds = loadDisabledIds();

function saveDisabledIds() {
  localStorage.setItem(DISABLED_KEY, JSON.stringify([...disabledIds]));
}

function svgIcon(inner, viewBox = "0 0 24 24") {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", viewBox);
  svg.setAttribute("width", "14");
  svg.setAttribute("height", "14");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "2");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.innerHTML = inner;
  return svg;
}

const POWER_ICON = '<path d="M12 2v9"/><path d="M18.36 6.64a9 9 0 1 1-12.73 0"/>';
const LINK_ICON =
  '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>';

function closeLightbox() {
  const overlay = document.querySelector(".lightbox");
  if (!overlay) return;
  const restore = overlay._restore;
  if (restore) restore();
  overlay.remove();
  document.removeEventListener("keydown", overlay._onKey);
}

function openLightbox(img, cam) {
  closeLightbox();

  const wrap = img.parentNode;
  const placeholder = document.createComment("lightbox-placeholder");
  wrap.replaceChild(placeholder, img);

  const overlay = document.createElement("div");
  overlay.className = "lightbox";

  const box = document.createElement("div");
  box.className = "lightbox-box";

  const closeBtn = document.createElement("button");
  closeBtn.className = "lightbox-close";
  closeBtn.type = "button";
  closeBtn.textContent = "×";
  closeBtn.setAttribute("aria-label", "Close");
  closeBtn.addEventListener("click", closeLightbox);

  const caption = document.createElement("div");
  caption.className = "lightbox-caption";
  caption.textContent = cam.name;

  box.appendChild(img);
  box.appendChild(closeBtn);
  box.appendChild(caption);
  overlay.appendChild(box);
  document.body.appendChild(overlay);

  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) closeLightbox();
  });
  const onKey = (e) => {
    if (e.key === "Escape") closeLightbox();
  };
  overlay._onKey = onKey;
  overlay._restore = () => {
    if (placeholder.parentNode) placeholder.parentNode.replaceChild(img, placeholder);
  };
  document.addEventListener("keydown", onKey);
}

function makeTile(cam, num) {
  const tile = document.createElement("figure");
  tile.className = "tile";
  tile.title = cam.name;

  const wrap = document.createElement("div");
  wrap.className = "video-wrap";

  let currentImg = null;
  let retryTimer = null;
  let enabled = !disabledIds.has(cam.id);

  const clearRetry = () => {
    if (retryTimer) {
      clearTimeout(retryTimer);
      retryTimer = null;
    }
  };

  const killImg = (imgEl) => {
    if (!imgEl) return;
    imgEl.onerror = null;
    imgEl.src = "";
  };

  const showPlaceholder = (text, cls) => {
    closeLightbox();
    killImg(wrap.querySelector("img"));
    wrap.innerHTML = "";
    const span = document.createElement("span");
    span.className = `placeholder ${cls}`;
    span.textContent = text;
    wrap.appendChild(span);
  };

  const handleError = () => {
    currentImg = null;
    if (!enabled) return;
    showPlaceholder("Offline", "offline");
    retryTimer = setTimeout(startStream, RETRY_MS);
  };

  function startStream() {
    clearRetry();
    killImg(wrap.querySelector("img"));
    wrap.innerHTML = "";
    const freshImg = document.createElement("img");
    freshImg.alt = cam.name;
    freshImg.onerror = handleError;
    freshImg.src = `/stream/${encodeURIComponent(cam.id)}?t=${Date.now()}`;
    wrap.appendChild(freshImg);
    currentImg = freshImg;
  }

  const stopStream = () => {
    clearRetry();
    currentImg = null;
    showPlaceholder("Feed off", "off");
  };

  const setEnabled = (next) => {
    enabled = next;
    tile.classList.toggle("disabled", !enabled);
    toggleBtn.classList.toggle("active", enabled);
    toggleBtn.setAttribute("aria-label", enabled ? "Turn camera feed off" : "Turn camera feed on");
    toggleBtn.title = enabled ? "Turn feed off" : "Turn feed on";
    if (enabled) {
      disabledIds.delete(cam.id);
      startStream();
    } else {
      disabledIds.add(cam.id);
      stopStream();
    }
    saveDisabledIds();
  };

  const controls = document.createElement("div");
  controls.className = "tile-controls";

  const toggleBtn = document.createElement("button");
  toggleBtn.type = "button";
  toggleBtn.className = "tile-btn toggle-btn";
  toggleBtn.appendChild(svgIcon(POWER_ICON));
  toggleBtn.addEventListener("click", () => setEnabled(!enabled));

  const linkBtn = document.createElement("button");
  linkBtn.type = "button";
  linkBtn.className = "tile-btn link-btn";
  linkBtn.setAttribute("aria-label", "Open camera's own URL");
  linkBtn.title = "Open camera URL";
  linkBtn.appendChild(svgIcon(LINK_ICON));
  linkBtn.addEventListener("click", () => {
    window.open(cam.click_url, "_blank", "noopener,noreferrer");
  });

  controls.appendChild(toggleBtn);
  controls.appendChild(linkBtn);

  wrap.addEventListener("click", () => {
    if (currentImg) openLightbox(currentImg, cam);
  });

  const label = document.createElement("figcaption");
  label.className = "label";
  label.textContent = `${cam.site} · Cam ${num}`;

  tile.appendChild(wrap);
  tile.appendChild(controls);
  tile.appendChild(label);

  if (enabled) {
    startStream();
  } else {
    tile.classList.add("disabled");
    showPlaceholder("Feed off", "off");
  }
  toggleBtn.classList.toggle("active", enabled);
  toggleBtn.title = enabled ? "Turn feed off" : "Turn feed on";
  toggleBtn.setAttribute("aria-label", enabled ? "Turn camera feed off" : "Turn camera feed on");

  return tile;
}

function render(cameras) {
  const root = document.getElementById("grid-root");
  root.innerHTML = "";

  if (cameras.length === 0) {
    root.innerHTML = '<p class="error">No cameras configured.</p>';
    return;
  }

  cameras.forEach((cam, i) => {
    root.appendChild(makeTile(cam, i + 1));
  });
}

fetch("/api/cameras")
  .then((r) => r.json())
  .then(render)
  .catch(() => {
    document.getElementById("grid-root").innerHTML =
      '<p class="error">Failed to load camera list.</p>';
  });
