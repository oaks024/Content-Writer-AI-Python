// Client-only helpers: clipboard, download, and content mutations that
// must not trigger another AI call.

function getMarkdown() {
  const raw = document.getElementById("raw-markdown");
  return raw ? raw.value : "";
}

function copyContent() {
  navigator.clipboard.writeText(getMarkdown());
}

function downloadContent() {
  const blob = new Blob([getMarkdown()], { type: "text/markdown" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "seo-content.md";
  a.click();
  URL.revokeObjectURL(a.href);
}

// Swap a humanized sentence into both the raw textarea and interactive view.
function applyHumanized(button) {
  const oldText = button.dataset.original;
  const newText = button.dataset.new;
  const raw = document.getElementById("raw-markdown");
  if (raw) raw.value = raw.value.split(oldText).join(newText);

  document.querySelectorAll("#interactive-content span").forEach((span) => {
    if (span.textContent.trim() === oldText.trim()) {
      span.textContent = newText;
      span.classList.remove("bg-amber-100", "hover:bg-amber-200", "cursor-pointer");
    }
  });
}

// Replace every detected cliché with its first suggested alternative.
function clearCliches(button) {
  const cliches = JSON.parse(button.dataset.cliches);
  const raw = document.getElementById("raw-markdown");
  cliches.forEach((c) => {
    const alt = c.alternatives.split(",")[0].trim();
    const rx = new RegExp("\\b" + c.word + "\\b", "gi");
    if (raw) raw.value = raw.value.replace(rx, alt);
    document.querySelectorAll("#interactive-content p, #interactive-content li")
      .forEach((el) => { el.innerHTML = el.innerHTML.replace(rx, alt); });
  });
  button.disabled = true;
  button.textContent = "Clichés replaced";
}
