async function refreshCartBadge() {
  const res = await fetch("/api/cart");
  const data = await res.json();
  const count = data.lines.reduce((sum, line) => sum + line.quantity, 0);
  const badge = document.getElementById("cart-count-badge");
  if (!badge) return;

  if (count > 0) {
    badge.textContent = String(count);
    badge.classList.remove("hidden");
    badge.classList.add("flex");
  } else {
    badge.classList.add("hidden");
    badge.classList.remove("flex");
  }
}

document.addEventListener("DOMContentLoaded", refreshCartBadge);
