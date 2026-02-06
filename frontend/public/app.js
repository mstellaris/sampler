const API = "/api/bookmarks";

const form = document.getElementById("bookmark-form");
const list = document.getElementById("bookmark-list");

async function loadBookmarks() {
  const res = await fetch(API);
  const bookmarks = await res.json();
  list.innerHTML = "";
  for (const b of bookmarks) {
    const li = document.createElement("li");

    const screenshotHtml = b.screenshot
      ? `<img class="thumbnail" src="/api/screenshots/${b.id}" alt="Preview">`
      : `<div class="thumbnail placeholder"></div>`;

    let linkedinHtml = "";
    if (b.linkedin_data) {
      const ld = b.linkedin_data;
      const imagesHtml = (ld.images || [])
        .map(img => `<img class="linkedin-img" src="/api/linkedin-images/${b.id}/${escapeHtml(img)}" alt="">`)
        .join("");
      linkedinHtml = `
        <div class="linkedin-card">
          <div class="linkedin-author">
            <strong>${escapeHtml(ld.author)}</strong>
            ${ld.headline ? `<span class="linkedin-headline">${escapeHtml(ld.headline)}</span>` : ""}
            ${ld.date ? `<span class="linkedin-date">${escapeHtml(ld.date)}</span>` : ""}
          </div>
          ${ld.text ? `<div class="linkedin-text">${escapeHtml(ld.text)}</div>` : ""}
          ${imagesHtml ? `<div class="linkedin-images">${imagesHtml}</div>` : ""}
        </div>
      `;
    }

    li.innerHTML = `
      <div class="info">
        <a href="${escapeHtml(b.url)}" target="_blank" rel="noopener">
          ${escapeHtml(b.title || b.url)}
        </a>
        <div class="meta">${new Date(b.created_at).toLocaleString()}</div>
        ${linkedinHtml}
      </div>
      ${screenshotHtml}
      <button class="delete" title="Delete">&times;</button>
    `;
    li.querySelector(".delete").addEventListener("click", () => deleteBookmark(b.id));
    list.appendChild(li);
  }
}

async function deleteBookmark(id) {
  await fetch(`${API}/${id}`, { method: "DELETE" });
  loadBookmarks();
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const url = document.getElementById("url").value.trim();
  const title = document.getElementById("title").value.trim();
  await fetch(API, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, title }),
  });
  form.reset();
  loadBookmarks();
});

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

loadBookmarks();
