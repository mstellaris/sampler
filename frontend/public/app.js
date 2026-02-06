const API = "/api/bookmarks";

const form = document.getElementById("bookmark-form");
const list = document.getElementById("bookmark-list");

async function loadBookmarks() {
  const res = await fetch(API);
  const bookmarks = await res.json();
  list.innerHTML = "";
  for (const b of bookmarks) {
    const li = document.createElement("li");
    li.innerHTML = `
      <div class="info">
        <a href="${escapeHtml(b.url)}" target="_blank" rel="noopener">
          ${escapeHtml(b.title || b.url)}
        </a>
        <div class="meta">${new Date(b.created_at).toLocaleString()}</div>
      </div>
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
