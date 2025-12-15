# Albert Heijn Bonus Extractor

## Technical Documentation

### Data Source

Albert Heijn uses a mobile API at `api.ah.nl` which provides full product data including bonus/discount information.

**Authentication Endpoint**: `https://api.ah.nl/mobile-auth/v1/auth/token/anonymous`
**Product Search Endpoint**: `https://api.ah.nl/mobile-services/product/search/v2`

### Authentication

Anonymous tokens are obtained by POSTing to the auth endpoint:
```json
{"clientId": "appie"}
```

Required headers for subsequent requests:
- `User-Agent: Appie/8.22.3`
- `Authorization: Bearer {access_token}`
- `X-Application: AHWEBSHOP`

### Data Extracted

The AH API provides rich product data. Each bonus product includes:

**Basic Info**:
- `webshopId`, `hqId` - Product identifiers
- `title` - Product name
- `brand` - Brand name
- `salesUnitSize` - Package size (e.g., "1.5 l", "500 g")

**Pricing**:
- `currentPrice` - Discounted bonus price
- `priceBeforeBonus` - Original price
- `unitPriceDescription` - Per-unit price (e.g., "prijs per liter €1.33")

**Bonus Details**:
- `isBonus` - Boolean flag for bonus items
- `bonusMechanism` - Type of discount (e.g., "1 + 1 gratis", "2e Halve Prijs", "2 voor 3.99")
- `bonusStartDate`, `bonusEndDate` - Validity period
- `discountLabels` - Discount percentage and description
- `isStapelBonus` - Stackable bonus indicator
- `isInfiniteBonus` - Unlimited validity bonus

**Category**:
- `mainCategory` - Main category (e.g., "Zuivel, eieren")
- `subCategory` - Subcategory (e.g., "Halfvolle melk")

**Images**:
- `images` - Array with multiple sizes (48, 80, 200, 400, 800 pixels)
- Images hosted on `static.ah.nl/dam/product/`

**Product Details**:
- `descriptionFull` - Full description
- `descriptionHighlights` - HTML formatted highlights
- `nutriscore` - Nutri-Score rating (A-E)
- `nix18` - Age-restricted product indicator
- `availableOnline` - Online availability

### How the Extractor Works

1. **Get Token**: Request anonymous access token from auth endpoint
2. **Paginate Search**: Iterate through product search results (200 per page)
3. **Filter Bonus**: Extract only products where `isBonus: true`
4. **Transform**: Convert to standard output format
5. **Save**: Output to `folder_data.json`

### Differences from Dirk/Hoogvliet/Lidl

| Aspect | Albert Heijn | Dirk | Hoogvliet | Lidl |
|--------|--------------|------|-----------|------|
| Data Source | Mobile API | NUXT embedded JSON | Publitas folder | Leaflets SPA (protected) |
| Auth | Anonymous token | None | None | N/A |
| Product Count | 200-400+ bonus | ~130 | ~100 | ~25 (non-food) |
| Has Discount % | ✅ Yes (calculated) | ✅ Yes | ✅ Yes | ❌ No |
| Has Nutri-Score | ✅ Yes | ❌ No | ❌ No | ❌ No |
| Has Categories | ✅ Rich | Basic | Basic | Basic |
| Image Quality | ✅ Up to 800px | ✅ Good | ✅ Good | ✅ Good |

### Important Notes

1. **Token Expiry**: Anonymous tokens expire after ~2 hours. Script gets fresh token each run.

2. **Rate Limiting**: The API doesn't seem to have strict rate limits for anonymous users, but be reasonable with request frequency.

3. **Bonus Types**: AH has various bonus mechanisms:
   - `1 + 1 gratis` - Buy one get one free
   - `2e Halve Prijs` - Second item half price
   - `2 voor X.XX` - Two for a fixed price
   - `X% volume voordeel` - Bulk discount
   - `2 stapelen tot X%` - Stackable discounts

4. **Product URL Pattern**: `https://www.ah.nl/producten/product/{webshopId}`

### Running the Extractor

```bash
cd /Users/yaronkra/Jarvis/tickets/001-supermarket/ah
python3 extract.py && python3 generate_html.py && open folder.html
```

### Dependencies

```bash
pip install requests
```

### Session Log

#### December 11, 2025
- Created initial extractor using mobile API
- Discovered API via GitHub resources and web research
- Anonymous authentication works reliably
- Rich data including nutri-score, discount percentages, and detailed categorization
