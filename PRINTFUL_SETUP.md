# Printful + Stripe Integration Setup Guide

## Overview
Your site now automatically creates Printful orders when customers complete payment through Stripe. Orders are sent to Printful for fulfillment with the customer's shipping address.

## How It Works

1. **Customer Checkout Flow:**
   - Customer adds products to cart → selects size
   - Clicks checkout → redirected to Stripe
   - Enters shipping address and payment info
   - Completes payment

2. **Order Fulfillment:**
   - Stripe sends webhook to your site: `/webhook/stripe`
   - Your site creates a Printful order with:
     - Product IDs and quantities
     - Selected sizes/variants
     - Customer shipping address
     - Order total
   - Printful receives the order and fulfills it
   - Customer receives tracking info from Printful

## Required Configuration

### 1. Stripe Webhook Setup

**In Stripe Dashboard:**
1. Go to Developers → Webhooks
2. Click "Add endpoint"
3. Enter URL: `https://music-news-site.onrender.com/webhook/stripe`
4. Select events to listen for: `checkout.session.completed`
5. Copy the "Signing secret" (starts with `whsec_`)

**In Render Dashboard:**
1. Go to your app → Environment
2. Add new variable:
   - Key: `STRIPE_WEBHOOK_SECRET`
   - Value: `whsec_xxx...` (paste the signing secret from Stripe)

### 2. Printful Product IDs

**IMPORTANT:** The demo products currently shown use placeholder IDs (1, 2, 3). For real orders, you need actual Printful sync_variant_ids.

**To get real product IDs:**

1. **Create Products in Printful:**
   - Go to your Printful dashboard
   - Create products: Design your t-shirts, hoodies, etc.
   - Sync them to your store

2. **Get Printful Product Data:**
   - The `get_printful_products()` function already fetches your products
   - It returns `sync_variant_id` for each product variant
   - These IDs are what get sent to Printful when creating orders

3. **Update Demo Products (Optional):**
   - If you want to test with demo products before setting up real ones:
   - Replace the IDs in `get_printful_products()` with real Printful variant IDs
   - Or just create real products in Printful and they'll automatically appear

### 3. Testing the Integration

**Test Mode (Recommended First):**
1. Use Stripe test mode keys (already configured)
2. Use Printful test mode
3. Make a test purchase with card: `4242 4242 4242 4242`
4. Check Render logs to see if Printful order was created
5. Check your Printful dashboard for the test order

**Check Logs:**
```bash
# In Render dashboard, view logs to see:
# - "Printful order created: [ORDER_ID]" ✅ Success
# - "Failed to create Printful order" ❌ Check error details
```

## Environment Variables Summary

Make sure these are all set in Render:

| Variable | Purpose | Example |
|----------|---------|---------|
| `STRIPE_SECRET_KEY` | Stripe API access | `sk_test_xxx` or `sk_live_xxx` |
| `STRIPE_PUBLISHABLE_KEY` | Client-side Stripe | `pk_test_xxx` or `pk_live_xxx` |
| `STRIPE_WEBHOOK_SECRET` | Verify webhook calls | `whsec_xxx` |
| `PRINTFUL_API_KEY` | Printful API access | Your API key |
| `PRINTFUL_STORE_ID` | Your store ID | From Printful |
| `SECRET_KEY` | Flask sessions | Random string |

## Troubleshooting

### No Printful order created
**Check:**
- Webhook is configured in Stripe
- Webhook secret is set in Render
- Printful API key is valid
- Product IDs match real Printful variants

### Order has wrong shipping address
**Check:**
- Shipping address collection is enabled in checkout (✅ already enabled)
- Stripe session is expanded with shipping_details

### Demo products instead of real products
**Solution:**
- Create products in Printful dashboard
- Sync them to your store
- The `get_printful_products()` function will automatically fetch them

## Going Live

When ready for production:

1. **Switch to Live Stripe Keys:**
   - Update `STRIPE_SECRET_KEY` to `sk_live_xxx`
   - Update `STRIPE_PUBLISHABLE_KEY` to `pk_live_xxx`
   - Create new webhook with live mode endpoint
   - Update `STRIPE_WEBHOOK_SECRET` with live webhook secret

2. **Printful Production:**
   - Ensure your Printful account is out of test mode
   - Verify billing is set up for fulfillment costs
   - Set competitive retail prices

3. **Test End-to-End:**
   - Make a real test purchase
   - Verify order appears in Printful
   - Check fulfillment process

## Order Flow Diagram

```
Customer Checkout
       ↓
Stripe Payment
       ↓
checkout.session.completed webhook
       ↓
Your Site (/webhook/stripe)
       ↓
create_printful_order()
       ↓
Printful Order Created
       ↓
Printful Fulfills & Ships
       ↓
Customer Receives Tracking
```

## Support

- **Stripe Webhooks:** https://stripe.com/docs/webhooks
- **Printful API:** https://developers.printful.com/docs/
- **Printful Orders:** https://developers.printful.com/docs/#operation/createOrder
