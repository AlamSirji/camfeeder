const RETRY_MS = 5000;

function makeTile(cam, num) {
  const tile = document.createElement("figure");
  tile.className = "tile";

  const wrap = document.createElement("div");
  wrap.className = "video-wrap";

  const img = document.createElement("img");
  img.alt = cam.name;

  const setOffline = () => {
    wrap.innerHTML = "";
    const span = document.createElement("span");
    span.className = "offline";
    span.textContent = "Offline";
    wrap.appendChild(span);
    setTimeout(() => retry(), RETRY_MS);
  };

  const retry = () => {
    wrap.innerHTML = "";
    const freshImg = img.cloneNode();
    freshImg.src = `/stream/${encodeURIComponent(cam.id)}?t=${Date.now()}`;
    freshImg.onerror = setOffline;
    wrap.appendChild(freshImg);
  };

  img.onerror = setOffline;
  img.src = `/stream/${encodeURIComponent(cam.id)}`;
  wrap.appendChild(img);

  const label = document.createElement("figcaption");
  label.className = "label";
  label.textContent = `${cam.site} · Cam ${num}`;

  tile.title = cam.name;
  tile.appendChild(wrap);
  tile.appendChild(label);
  tile.addEventListener("click", () => {
    window.open(cam.click_url, "_blank", "noopener,noreferrer");
  });

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
