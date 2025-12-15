# Jumbo Promotions Extractor

## Technical Documentation

### Data Source

Jumbo embeds their promotion data directly in the offers page HTML at `https://www.jumbo.com/aanbiedingen/nu`.

**Main Page**: `https://www.jumbo.com/aanbiedingen/nu`
**Individual Promo**: `https://www.jumbo.com/aanbiedingen/{slug}/{id}`

### How the Extractor Works

1. **Fetch main page**: Download the offers page HTML
2. **Extract embedded data**: Parse promotion entries from the embedded JavaScript data
3. **Extract images**: Find promotional images in the HTML
4. **Fetch details**: Visit each promotion page for additional details (discount tags, validity)
5. **Save output**: Write to `folder_data.json`

### Data Format in HTML

The promotion data is embedded in a specific format:
```
"Promotion","ID","UUID","TITLE","SUBTITLE",...
```

Example:
```
"Promotion","3012975","yo0KY7TZ3H0AAAGaQAsZoE3O","Alle Viennetta","M.u.v. Viennetta salted caramel"
```

### Data Extracted

**From main page**:
- `id` - Promotion ID (e.g., "3012975")
- `uuid` - Unique identifier
- `title` - Promotion title (e.g., "Alle Viennetta")
- `subtitle` - Additional description
- `url` - Link to promotion detail page
- `image_url` - Promotional image

**From detail pages**:
- `discount_tag` - Discount text (e.g., "1+1 gratis", "2 voor 5,00")
- `validity` - Validity period (e.g., "wo 10 t/m di 16 dec")

### Discount Types Found

Common discount patterns at Jumbo:
- `1+1 gratis` - Buy one get one free
- `2+1 gratis` - Buy two get one free
- `2 voor X,XX` - Two for fixed price
- `voor X,XX` - Special price
- `X,XX korting` - Fixed discount amount
- `X% korting` - Percentage discount
- `Combikorting` - Combined products discount

### Differences from Other Supermarkets

| Aspect | Jumbo | Albert Heijn | Dirk | Hoogvliet |
|--------|-------|--------------|------|-----------|
| Data Source | Embedded HTML | Mobile API | NUXT JSON | Publitas API |
| Auth Required | No | Anonymous token | No | No |
| Product Count | ~60-100 promos | ~1000 bonus | ~130 | ~100 |
| Has Prices | No (promo only) | Yes | Yes | Yes |
| Image Quality | Good | Excellent | Good | Good |

### Important Notes

1. **Promotions vs Products**: Jumbo's offers page shows promotions (grouped offers) rather than individual products. Each promotion may include multiple products.

2. **Rate Limiting**: The script fetches detail pages sequentially to avoid overwhelming the server.

3. **Mobile API**: The mobile API at `mobileapi.jumbo.com/v17` exists but was unresponsive during testing. The HTML scraping approach is more reliable.

4. **Weekly Updates**: Promotions typically change on Wednesdays.

### Running the Extractor

```bash
cd /Users/yaronkra/Jarvis/tickets/001-supermarket/jumbo
python3 extract.py && python3 generate_html.py && open folder.html
```

### Dependencies

```bash
pip install requests
```

### Session Log

#### December 11, 2025
- Created initial extractor using HTML scraping approach
- Found 106 unique promotion IDs, ~67 complete entries
- Mobile API (`mobileapi.jumbo.com`) was unresponsive
- Data extracted includes titles, subtitles, images, discount tags
- HTML viewer created with search and filter functionality
