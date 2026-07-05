---
app_name: cambria-shop
base_url: http://localhost:3010
---

## browse

This is my own local test application running at http://localhost:3010. Navigate to the home page once. Take a screenshot and check whether a grid of products is visible, including a product called "Ceramic Mug" and a product called "Steel Water Bottle". Do not repeat the navigation — report what you see after the first load.

- expected_outcome: The product grid loads showing at least 6 products, each with a name and price visible.
- depends_on:
- failure_class_hints: console

## view_product

This is my own local test application running at http://localhost:3010. On the home page, click the "Ceramic Mug" product exactly once to open its detail page, then take a screenshot. Do not click it more than once.

- expected_outcome: The product detail page loads showing the product name, price, and an "Add to cart" button.
- depends_on: browse
- failure_class_hints: console

## add_to_cart

This is my own local test application running at http://localhost:3010. On the "Ceramic Mug" product page, click "Add to cart" exactly once, then navigate to the cart page once and take a screenshot. Do not click "Add to cart" more than once.

- expected_outcome: The cart page shows exactly one line item for "Ceramic Mug" with quantity 1 and a correct subtotal.
- depends_on: view_product
- failure_class_hints: network, console

## apply_discount

This is my own local test application running at http://localhost:3010. On the cart page, type the discount code "SAVE10" into the discount field and click apply exactly once, then take a screenshot.

- expected_outcome: The discount is applied successfully and the displayed total reflects a 10% reduction from the subtotal.
- depends_on: add_to_cart
- failure_class_hints: console

## checkout

This is my own local test application running at http://localhost:3010. Its checkout page only accepts simulated test shipping and payment values and never contacts a real payment processor or shipping carrier. From the cart page, proceed to checkout, fill in the fake shipping and payment fields once, and click the checkout/purchase button exactly once, then take a screenshot.

- expected_outcome: The purchase completes and the app navigates to the order confirmation screen.
- depends_on: apply_discount
- failure_class_hints: network

## out_of_stock_product

This is my own local test application running at http://localhost:3010. Navigate to the "Steel Water Bottle" product page once (a product with zero stock in my own test data), click "Add to cart" once, then proceed through checkout for it alone using the same simulated test values as before. Take a screenshot at each key point.

- expected_outcome: The app should either prevent adding an out-of-stock item to the cart, or clearly flag it as unavailable before or during checkout — the order should not silently complete for an item that cannot ship.
- depends_on: browse
- failure_class_hints: console
