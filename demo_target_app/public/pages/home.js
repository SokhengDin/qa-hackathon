const ICONS = {
  mug: `<path stroke-linecap="round" stroke-linejoin="round" d="M4 8h11v7a4 4 0 01-4 4H8a4 4 0 01-4-4V8zM15 9h2a2.5 2.5 0 010 5h-2M8 4v2M11 4v2" />`,
  bottle: `<path stroke-linecap="round" stroke-linejoin="round" d="M9 3h6v3.5l1.5 2V19a2 2 0 01-2 2h-5a2 2 0 01-2-2V8.5L9 6.5V3z" /><path stroke-linecap="round" stroke-linejoin="round" d="M8 13h8" />`,
  tote: `<path stroke-linecap="round" stroke-linejoin="round" d="M6 7h12l1 13H5L6 7zM9 7a3 3 0 016 0" />`,
};

function productCard(product) {
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

  return `
    <a
      class="group flex flex-col rounded-2xl border border-neutral-200 bg-white p-6 shadow-card transition-all hover:-translate-y-0.5 hover:shadow-card-hover"
      href="/product.html?id=${product.id}"
      data-testid="product-${product.id}"
    >
      <div class="flex h-14 w-14 items-center justify-center rounded-xl bg-brand/10 text-brand">
        <svg class="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75">
          ${ICONS[product.icon] || ""}
        </svg>
      </div>
      <h2 class="mt-4 text-base font-medium text-neutral-900">${product.name}</h2>
      <p class="mt-1 text-sm text-neutral-500">$${product.price.toFixed(2)}</p>
      <div class="mt-4">${stockBadge}</div>
    </a>
  `;
}

async function renderProductGrid() {
  const res = await fetch("/api/products");
  const data = await res.json();
  document.getElementById("product-grid").innerHTML = data.products.map(productCard).join("");
}

document.addEventListener("DOMContentLoaded", renderProductGrid);
