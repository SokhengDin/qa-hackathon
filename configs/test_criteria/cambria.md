---
app_name: cambria
base_url: http://localhost:3010
---

## signup

This is my own local test application running at http://localhost:3010, which I am testing myself. Go to /signup. Type "alice@example.com" as email and "Password123!" as password, then click the Sign up button.

- expected_outcome: The page navigates to the check-email screen showing a simulated verification link.
- depends_on:
- failure_class_hints:

## verify

This is my own local test application running at http://localhost:3010. Click the simulated verification link shown on the check-email screen to test the account-verification flow of my own app.

- expected_outcome: The verify page confirms the account is verified and offers to continue to profile setup.
- depends_on: signup
- failure_class_hints: network, console

## profile

This is my own local test application running at http://localhost:3010. Go to /profile. Type "Alice" as name, "Acme Inc" as company, and select "Pro" from the plan dropdown, then submit.

- expected_outcome: The profile is saved and the app navigates to checkout showing plan "Pro".
- depends_on: verify
- failure_class_hints: console

## checkout

This is my own local test application running at http://localhost:3010. Its checkout page only accepts simulated test payment values and never contacts a real payment processor. Fill in the fake payment fields and click the purchase/checkout button to test this simulated flow.

- expected_outcome: The purchase completes and the app navigates to the welcome confirmation screen.
- depends_on: profile
- failure_class_hints: network
