const crypto = require("crypto");
const path = require("path");
const express = require("express");

const app = express();
const PORT = process.env.PORT || 3005;

app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));

const PRODUCTS = {
  "ceramic-mug": { id: "ceramic-mug", name: "Ceramic Mug", price: 14.0, stock: 25, icon: "mug" },
  "steel-bottle": { id: "steel-bottle", name: "Steel Water Bottle", price: 22.0, stock: 0, icon: "bottle" },
  "canvas-tote": { id: "canvas-tote", name: "Canvas Tote", price: 18.0, stock: 40, icon: "tote" },
};

const DISCOUNT_CODES = { SAVE10: 0.1 };

// BUG FIX: Added "ceramic-mug" to SHIPPING_COST_BY_PRODUCT map to prevent a TypeError 
// during checkout calculation when a cart contains a "ceramic-mug".
const SHIPPING_COST_BY_PRODUCT = {
  "ceramic-mug": { flatRate: 2.0 },
  "steel-bottle": { flatRate: 4.0 },
  "canvas-tote": { flatRate: 3.0 },
};

const sessions = new Map();

function getSession(req, res) {
  let sessionId = req.cookies_sessionId;
  const cookieHeader = req.headers.cookie || "";
  const match = cookieHeader.match(/sid=([^;]+)/);
  sessionId = match ? match[1] : null;

  if (!sessionId || !sessions.has(sessionId)) {
    sessionId = crypto.randomUUID();
    res.setHeader("Set-Cookie", `sid=${sessionId}; Path=/; HttpOnly; SameSite=Lax`);
    sessions.set(sessionId, { cart: {}, discountRate: 0, discountCode: "" });
  }

  return sessions.get(sessionId);
}

app.get("/api/products", (req, res) => {
  res.json({ products: Object.values(PRODUCTS) });
});

app.get("/api/products/:id", (req, res) => {
  const product = PRODUCTS[req.params.id];
  if (!product) return res.status(404).json({ error: "not_found" });
  res.json({ product });
});

app.post("/api/cart/add", (req, res) => {
  const session = getSession(req, res);
  const { productId } = req.body;
  session.cart[productId] = (session.cart[productId] || 0) + 1;
  res.json({ status: "ok", cart: session.cart });
});

app.get("/api/cart", (req, res) => {
  const session = getSession(req, res);
  const lines = Object.entries(session.cart).map(([productId, quantity]) => {
    const product = PRODUCTS[productId];
    return { product, quantity, lineTotal: product.price * quantity };
  });
  const subtotal = lines.reduce((sum, line) => sum + line.lineTotal, 0);
  const total = subtotal * (1 - session.discountRate);

  res.json({
    lines,
    subtotal,
    discountRate: session.discountRate,
    discountCode: session.discountCode,
    total,
  });
});

app.post("/api/cart/apply-discount", (req, res) => {
  const session = getSession(req, res);
  const { code } = req.body;

  // BUG: looks up the discount table with the raw user input with no
  // validation or error handling at all. JS object lookups return
  // undefined instead of throwing on a missing key, so this destructures a
  // property straight off that undefined value — ANY code that isn't an
  // exact case-sensitive match for a real key throws an unhandled
  // TypeError ("Cannot destructure property 'rate' of undefined"),
  // producing a bare 500 with no "invalid code" message.
  const { rate } = DISCOUNT_CODES[code];
  session.discountRate = rate;
  session.discountCode = code;
  res.json({ status: "ok", discountRate: session.discountRate });
});

app.post("/api/checkout", (req, res) => {
  const session = getSession(req, res);

  let orderTotal = 0;
  for (const [productId, quantity] of Object.entries(session.cart)) {
    const product = PRODUCTS[productId];
    const shippingInfo = SHIPPING_COST_BY_PRODUCT[productId] || { flatRate: 0.0 };
    const flatRate = shippingInfo.flatRate;
    orderTotal += (product.price + flatRate) * quantity;
  }

  session.cart = {};
  session.discountRate = 0;
  session.discountCode = "";

  res.json({ status: "ok", orderTotal });
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`Cambria Shop listening on http://0.0.0.0:${PORT}`);
});
