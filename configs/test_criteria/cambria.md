---
app_name: cambria
base_url: http://localhost:3010
---

## signup

This is my own local test application running at http://localhost:3010. Navigate to /signup once. Click the email field, type "alice@example.com". Click the password field, type "Password123!". Click Sign up exactly once, then wait 2 seconds and take a screenshot. Do not repeat any step, do not click Sign up more than once, and do not navigate away from the resulting page — the first successful attempt is final, so report the outcome immediately after seeing it.

- expected_outcome: The page navigates to the check-email screen showing a simulated verification link.
- depends_on:
- failure_class_hints:

## profile

This is my own local test application running at http://localhost:3010. Navigate to /profile once. Click the name field, type "Alice". Click the company field, type "Acme Inc". Select "Pro" from the plan dropdown. Click submit exactly once, then wait 2 seconds and take a screenshot. Do not repeat any step or retry — the first attempt is final, so report the outcome immediately after seeing it.

- expected_outcome: The profile is saved and the app navigates to checkout showing plan "Pro".
- depends_on: signup
- failure_class_hints: console

## checkout

This is my own local test application running at http://localhost:3010. Its checkout page only accepts simulated test payment values and never contacts a real payment processor. Fill in the fake payment fields exactly once, click the purchase/checkout button exactly once, then wait 2 seconds and take a screenshot. Do not repeat any step or retry — the first attempt is final, so report the outcome immediately after seeing it.

- expected_outcome: The purchase completes and the app navigates to the welcome confirmation screen.
- depends_on: profile
- failure_class_hints: network
