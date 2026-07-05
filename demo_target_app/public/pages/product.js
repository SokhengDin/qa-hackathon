const ICONS = {
  mug: `<path stroke-linecap="round" stroke-linejoin="round" d="M4 8h11v7a4 4 0 01-4 4H8a4 4 0 01-4-4V8zM15 9h2a2.5 2.5 0 010 5h-2M8 4v2M11 4v2" />`,
  bottle: `<path stroke-linecap="round" stroke-linejoin="round" d="M9 3h6v3.5l1.5 2V19a2 2 0 01-2 2h-5a2 2 0 01-2-2V8.5L9 6.5V3z" /><path stroke-linecap="round" stroke-linejoin="round" d="M8 13h8" />`,
  tote: `<path stroke-linecap="round" stroke-linejoin="round" d="M6 7h12l1 13H5L6 7zM9 7a3 3 0 016 0" />`,
};

function getProductId() {
  return new URLSearchParams(window.location.search).get("id");
}

function renderProduct(product) {
  const stockBadge =
    product.stock === 0
      ? `<span class="inline-flex items-center gap-1 rounded-full bg-out-of-stock/10 px-2.5 py-1 text-xs font-medium text-out-of-stock">
           <svg class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
             <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
           </svg>
           Out of stock
         </span>`
      : `<span class="inline-flex items-center gap-1 rounded-full bg-neutral-100 px-2.5 py-1 text-xs font-medium text-neutral-600">
           <svg class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
             <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
           </svg>
           ${product.stock} in stock
         </span>`;

  document.getElementById("product-detail").innerHTML = `
    <div class="flex h-16 w-16 items-center justify-center rounded-xl bg-brand/10 text-brand">
      <svg class="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75">
        ${ICONS[product.icon] || ""}
      </svg>
    </div>
    <h1 class="mt-5 text-2xl font-semibold tracking-tight">${product.name}</h1>
    <p class="mt-2 text-xl text-neutral-700">$${product.price.toFixed(2)}</p>
    <div class="mt-3">${stockBadge}</div>
    <button
      id="add-to-cart-button"
      type="button"
      class="mt-8 inline-flex items-center gap-2 rounded-lg bg-brand px-5 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-brand-dark"
      data-testid="add-to-cart"
    >
      <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M3 3h2l.4 2M7 13h10l3.6-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17M17 13v4a2 2 0 01-2 2H9a2 2 0 01-2-2v-4m10 0H7" />
      </svg>
      Add to cart
    </button>
  `;

  document.getElementById("add-to-cart-button").addEventListener("click", async () => {
    await fetch("/api/cart/add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ productId: product.id }),
    });
    window.location.href = "/cart.html";
  });
}

async function loadProduct() {
  const id = getProductId();
  const res = await fetch(`/api/products/${id}`);
  if (!res.ok) {
    document.getElementById("product-detail").innerHTML = `<p class="text-sm text-neutral-500">Product not found.</p>`;
    return;
  }
  const data = await res.json();
  renderProduct(data.product);
}

document.addEventListener("DOMContentLoaded", loadProduct);
