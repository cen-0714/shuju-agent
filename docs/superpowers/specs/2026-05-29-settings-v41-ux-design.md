# Settings V4.1 UX Design

## Goal

Make the Settings page usable for internal Amazon store setup without requiring the user to understand API payload formats or backend field names.

## Scope

This change only updates the Settings page and tests. It does not add SP-API data pulling, SaaS authorization, public callback URLs, login permissions, or async jobs.

## Problems To Fix

- Seller account and marketplace forms submit as browser form data, but the backend APIs require JSON request bodies.
- Failed form submissions navigate the browser to raw API JSON error pages.
- The page does not explain that Amazon's "卖家记号 / Merchant Token" is the value used for the system's seller id and SP-API authorization identity.
- Store setup, SP-API authorization, optional marketplace setup, and LLM settings are visually stacked without clear order.

## Design

The Settings page will be reorganized into a clearer internal setup flow:

1. Store profile
   - User-facing copy: "卖家记号 / Merchant Token".
   - The form sends JSON to `POST /api/settings/seller-accounts`.
   - Success and failure are displayed inline, without navigating away.
   - On success, the returned seller account id is shown so the user can use it for marketplace setup when needed.

2. SP-API self authorization
   - User-facing copy explains that "卖方合作伙伴身份" should use the same "卖家记号 / Merchant Token".
   - The form continues sending JSON to `POST /api/auth/amazon/self-authorizations`.
   - Success and failure are displayed inline.

3. Optional marketplace setup
   - Copy states that marketplace setup can be skipped while only testing SP-API authorization.
   - The form sends JSON to `POST /api/settings/marketplaces`.
   - US marketplace defaults stay prefilled.

4. LLM settings
   - Kept visually separate and marked as report-analysis configuration, not required for Amazon authorization.

## Error Handling

Each form catches failed responses and shows the API error message inline. The browser should remain on `/settings`.

## Testing

- Update the existing web page test to assert clearer labels and helper text.
- Add assertions that old `method="post" action="/api/settings/seller-accounts"` and `method="post" action="/api/settings/marketplaces"` forms are gone.
- Existing API tests remain unchanged because the API contract stays JSON.
