// Videos made in this browser. Only metadata is stored here; the MP4 lives on the server (free hosting clears it on restart).
const KEY = "reelwright.projects";

export function loadProjects() {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || "[]");
    return Array.isArray(v) ? v : [];
  } catch {
    return [];
  }
}
function save(list) {
  try { localStorage.setItem(KEY, JSON.stringify(list.slice(0, 40))); } catch { /* storage blocked: ignore */ }
}
export function addProject(p) {
  const list = [p, ...loadProjects().filter((x) => x.id !== p.id)];
  save(list);
  return list.slice(0, 40);
}
export function removeProject(id) {
  const list = loadProjects().filter((x) => x.id !== id);
  save(list);
  return list;
}
