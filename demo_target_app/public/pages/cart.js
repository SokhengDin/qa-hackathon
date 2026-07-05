function renderCartLines(lines) {
  return lines
    .map(
      (line) => `
        <div class="flex items-center justify-between px-6 py-5">
          <div>
            <p class="font-medium text-neutral-900">${line.product.name}</p>
            <p class="mt-0.5 text-sm text-neutral-500">Qty ${line.quantity}</p>
          </div>
          <p class="font-medium text-neutral-900">$${line.lineTotal.toFixed(2)}</p>
        </div>
      `
    )
    .join("");
}

function renderSummary(cart) {
  const discountLine =
    cart.discountRate > 0
      ? `<div class="flex items-center justify-between text-sm text-brand">
           <span class="flex items-center gap-1">
             <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
               <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
             </svg>
             Discount (${cart.discountCode})
           </span>
           <span>-${Math.round(cart.discountRate * 100)}%</span>
         </div>`
      : "";

  return `
    <div class="flex justify-between text-sm text-neutral-600">
      <span>Subtotal</span>
      <span>$${cart.subtotal.toFixed(2)}</span>
    </div>
    ${discountLine}
    <div class="flex justify-between border-t border-neutral-200 pt-3 text-base font-semibold text-neutral-900">
      <span>Total</span>
      <span data-testid="cart-total">$${cart.total.toFixed(2)}</span>
    </div>
  `;
}

async function loadCart() {
  const res = await fetch("/api/cart");
  const cart = await res.json();

  if (cart.lines.length === 0) {
    document.getElementById("cart-empty").classList.remove("hidden");
    document.getElementById("cart-empty").classList.add("flex");
    document.getElementById("cart-filled").classList.add("hidden");
    return;
  }

  document.getElementById("cart-empty").classList.add("hidden");
  document.getElementById("cart-filled").classList.remove("hidden");
  document.getElementById("cart-lines").innerHTML = renderCartLines(cart.lines);
  document.getElementById("cart-summary").innerHTML = renderSummary(cart);
  document.getElementById("discount-code-input").value = cart.discountCode || "";
}

document.getElementById("discount-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const code = document.getElementById("discount-code-input").value;
  await fetch("/api/cart/apply-discount", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
  await loadCart();
});

document.getElementById("checkout-button").addEventListener("click", async () => {
  const res = await fetch("/api/checkout", { method: "POST" });

  if (!res.ok) {
    document.getElementById("cart-filled").classList.add("hidden");
    document.getElementById("checkout-error").classList.remove("hidden");
    return;
  }

  const data = await res.json();
  document.getElementById("cart-filled").classList.add("hidden");
  document.getElementById("confirmation-total").textContent = `$${data.orderTotal.toFixed(2)}`;
  document.getElementById("checkout-confirmation").classList.remove("hidden");
  refreshCartBadge();
});

document.addEventListener("DOMContentLoaded", loadCart);
