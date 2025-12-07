# Merchbar Integration Guide

## Overview
The Music Hub merch store now uses **Merchbar**, the world's largest marketplace for official band merchandise, instead of custom print-on-demand through Printful. This provides access to thousands of authentic artist stores with no inventory management required.

## How It Works

### 1. **Curated Artist Selection**
- The merch page displays 12 hand-picked popular artists
- Each artist card links directly to their official Merchbar store
- Categories include: Pop, Rock, Hip-Hop, Metal, R&B, and more

### 2. **Affiliate Links**
All Merchbar links include the affiliate tracking parameter: `?ref=musichub`

Example:
```
https://www.merchbar.com/pop/taylor-swift?ref=musichub
https://www.merchbar.com/hard-rock-metal/metallica?ref=musichub
```

### 3. **Purchase Flow**
1. User clicks on artist card on your merch page
2. Opens Merchbar in new tab with affiliate tracking
3. User browses official merchandise
4. Merchbar handles checkout, payment, and shipping
5. You earn affiliate commission on completed sales

## Featured Artists

Current lineup (easily expandable in `get_merchbar_products()`):

- **Pop**: Taylor Swift, Billie Eilish, Harry Styles, Olivia Rodrigo
- **Rock/Metal**: Metallica, Nirvana, Pink Floyd, Led Zeppelin
- **Hip-Hop/R&B**: The Weeknd, Drake, Bad Bunny
- **Classic**: The Beatles

## Technical Implementation

### Backend (`app.py`)
```python
def get_merchbar_products():
    """Get curated band merchandise from Merchbar."""
    products = [
        {
            "id": "artist-slug",
            "artist": "Artist Name",
            "category": "Genre",
            "description": "Description of available merch",
            "image": "image_url",
            "merchbar_url": "https://www.merchbar.com/genre/artist?ref=musichub",
            "featured": True/False
        },
        # ... more artists
    ]
    return products
```

### Frontend (`templates/merch.html`)
- Clean card-based grid layout
- Category filtering (All, Pop, Rock, etc.)
- Hover effects showing "Shop Now →"
- Mobile-responsive design
- Footer with Merchbar branding and affiliate disclosure

### Disabled Code
The previous Stripe + Printful e-commerce system has been disabled but kept in comments for reference:
- Cart API endpoints (`/api/cart`)
- Stripe checkout routes (`/create-checkout-session`)
- Printful order creation functions
- Cart sidebar and JavaScript

## Adding New Artists

To add more artists to the merch page:

1. Open `app.py`
2. Find `get_merchbar_products()` function
3. Add new artist dictionary to the `products` list:

```python
{
    "id": "artist-slug",
    "artist": "Artist Name",
    "category": "Genre Category",
    "description": "Brief description of merch available",
    "image": "https://unsplash.com/photo-id?w=500&q=80",
    "merchbar_url": "https://www.merchbar.com/genre/artist-slug?ref=musichub",
    "featured": False  # Set to True for priority placement
}
```

4. Commit and deploy

## Merchbar Affiliate Program

### Sign Up
1. Visit Merchbar's affiliate program page
2. Apply with your Music Hub site details
3. Get approved for affiliate commissions

### Commission Tracking
- Merchbar tracks clicks via the `?ref=musichub` parameter
- Standard affiliate commission on completed purchases
- Access dashboard for performance metrics

### Best Practices
- Keep artist selection current with trending artists
- Update seasonally (holiday merch, tour dates, etc.)
- Add artists featured in your news articles
- Test affiliate links regularly

## Benefits Over Custom E-Commerce

✅ **No Inventory Management**
- No need to stock or ship products
- Merchbar handles all fulfillment

✅ **Official Merchandise Only**
- All products are officially licensed
- Direct partnerships with record labels and artists

✅ **Established Infrastructure**
- Trusted payment processing
- Proven shipping and customer service
- Return/exchange policies handled by Merchbar

✅ **Massive Selection**
- Access to thousands of artists
- Constantly updated inventory
- Exclusive and limited edition items

✅ **Lower Risk**
- No upfront inventory costs
- No payment processing liability
- Passive income through affiliate commissions

## Maintenance

### Regular Updates
- Add new trending artists monthly
- Update images with high-quality photos
- Verify all affiliate links work correctly
- Monitor Merchbar for new featured artists

### SEO Optimization
- Page is already optimized with relevant keywords
- Consider creating artist-specific landing pages
- Link to merch page from related news articles

### Performance Monitoring
- Track which artists get the most clicks
- A/B test different artist selections
- Analyze conversion rates in Merchbar dashboard
- Adjust featured artists based on performance

## Reverting to Custom E-Commerce

If you need to switch back to Stripe + Printful:

1. Uncomment the disabled code in `app.py`:
   - Stripe imports
   - Checkout routes
   - Cart API
   - Printful order creation

2. Restore `templates/merch_old.html.bak` to `merch.html`

3. Re-install dependencies:
   ```bash
   pip install stripe
   ```

4. Set environment variables:
   - `STRIPE_SECRET_KEY`
   - `STRIPE_PUBLISHABLE_KEY`
   - `PRINTFUL_API_KEY`
   - `PRINTFUL_STORE_ID`

5. Commit and deploy

## Support

For questions about:
- **Merchbar Integration**: Contact Merchbar affiliate support
- **Technical Implementation**: Review this guide or check `app.py` comments
- **Adding Artists**: See "Adding New Artists" section above

---

**Last Updated**: December 6, 2025
**Integration Version**: 1.0
**Status**: ✅ Active and Deployed
