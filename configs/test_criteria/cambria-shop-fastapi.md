---
app_name: cambria-shop
base_url: http://localhost:8009
---

## browse

This is my own local test application running at http://localhost:8009. Navigate to the home page once. Take a screenshot and check whether a grid of products is visible, including a product called "Ceramic Mug". Do not repeat the navigation — report what you see after the first load.

- expected_outcome: The product grid loads showing 3 products, each with a name, price, and stock status visible.
- depends_on:
- failure_class_hints: console

## apply_discount

This is my own local test application running at http://localhost:8009. On the home page, click the "Ceramic Mug" product exactly once to open its detail page. Click "Add to cart" exactly once, then navigate to the cart page once. On the cart page, type the discount code "save10" (all lowercase) into the discount field and click apply exactly once, then take a screenshot. Do not repeat any step.

- expected_outcome: The discount is applied successfully and the displayed total reflects a 10% reduction from the subtotal, or the app clearly shows an "invalid code" message.
- depends_on: browse
- failure_class_hints: console, network
