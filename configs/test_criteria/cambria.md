---
app_name: cambria
base_url: http://localhost:3010
---

## signup

Go to /signup. Type "alice@example.com" as email and "Password123!" as password, then click the Sign up button.

- expected_outcome: The page navigates to the check-email screen showing a simulated verification link.
- depends_on:
- failure_class_hints:

## verify

Click the verification link shown on the check-email screen.

- expected_outcome: The verify page confirms the account is verified and offers to continue to profile setup.
- depends_on: signup
- failure_class_hints: network, console

## profile

Go to /profile. Type "Alice" as name, "Acme Inc" as company, and select "Pro" from the plan dropdown, then submit.

- expected_outcome: The profile is saved and the app navigates to checkout showing plan "Pro".
- depends_on: verify
- failure_class_hints: console

## checkout

On the checkout page, fill in the fake payment fields and click the purchase/checkout button.

- expected_outcome: The purchase completes and the app navigates to the welcome confirmation screen.
- depends_on: profile
- failure_class_hints: network
