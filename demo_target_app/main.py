from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI(title="Cambria Shop")
app.add_middleware(SessionMiddleware, secret_key="dev-only-not-a-real-secret")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

PRODUCTS = {
    "ceramic-mug": {
        "id": "ceramic-mug",
        "name": "Ceramic Mug",
        "price": 14.00,
        "stock": 25,
        "icon": "mug",
    },
    "steel-bottle": {
        "id": "steel-bottle",
        "name": "Steel Water Bottle",
        "price": 22.00,
        "stock": 0,
        "icon": "bottle",
    },
    "canvas-tote": {
        "id": "canvas-tote",
        "name": "Canvas Tote",
        "price": 18.00,
        "stock": 40,
        "icon": "tote",
    },
}

DISCOUNT_CODES = {
    "SAVE10": 0.10,
}

# BUG: missing an entry for "ceramic-mug" — whoever added this table forgot
# the most popular product. Any checkout that includes it throws an
# unhandled KeyError, which FastAPI turns into a bare 500 with a traceback
# in the server log and no user-facing message.
SHIPPING_COST_BY_PRODUCT = {
    "steel-bottle": 4.00,
    "canvas-tote": 3.00,
}


def get_cart(request: Request) -> dict:
    return request.session.setdefault("cart", {})


def cart_count(request: Request) -> int:
    return sum(get_cart(request).values())


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request,
        "home.html",
        {"products": PRODUCTS.values(), "cart_count": cart_count(request)},
    )


@app.get("/product/{product_id}")
def view_product(request: Request, product_id: str):
    product = PRODUCTS[product_id]
    return templates.TemplateResponse(
        request,
        "product.html",
        {"product": product, "cart_count": cart_count(request)},
    )


@app.post("/cart/add")
def add_to_cart(request: Request, product_id: str = Form(...)):
    cart = get_cart(request)
    cart[product_id] = cart.get(product_id, 0) + 1
    request.session["cart"] = cart
    return RedirectResponse(url="/cart", status_code=303)


@app.get("/cart")
def view_cart(request: Request):
    cart = get_cart(request)
    lines = []
    subtotal = 0.0
    for product_id, quantity in cart.items():
        product = PRODUCTS[product_id]
        line_total = product["price"] * quantity
        subtotal += line_total
        lines.append({"product": product, "quantity": quantity, "line_total": line_total})

    discount_rate = request.session.get("discount_rate", 0.0)
    discount_code = request.session.get("discount_code", "")
    total = subtotal * (1 - discount_rate)

    return templates.TemplateResponse(
        request,
        "cart.html",
        {
            "lines": lines,
            "subtotal": subtotal,
            "discount_rate": discount_rate,
            "discount_code": discount_code,
            "total": total,
            "cart_count": cart_count(request),
        },
    )


@app.post("/cart/apply-discount")
def apply_discount(request: Request, code: str = Form(...)):
    # BUG: looks up the discount table with the raw user input with no
    # validation or error handling at all, so ANY code that isn't an exact
    # case-sensitive match for a real key throws an unhandled KeyError,
    # which FastAPI turns into a bare 500 with a traceback in the server log
    # and no user-facing message. There's no try/except and no "invalid code"
    # branch — the fix is to validate the code exists before using it.
    rate = DISCOUNT_CODES[code]
    request.session["discount_rate"] = rate
    request.session["discount_code"] = code
    return RedirectResponse(url="/cart", status_code=303)


@app.post("/checkout")
def checkout(request: Request):
    cart = get_cart(request)

    order_total = 0.0
    for product_id, quantity in cart.items():
        product = PRODUCTS[product_id]
        shipping = SHIPPING_COST_BY_PRODUCT[product_id]
        order_total += (product["price"] + shipping) * quantity

    request.session["cart"] = {}
    request.session["discount_rate"] = 0.0
    request.session["discount_code"] = ""

    return templates.TemplateResponse(
        request,
        "confirmation.html",
        {"order_total": order_total, "cart_count": 0},
    )
