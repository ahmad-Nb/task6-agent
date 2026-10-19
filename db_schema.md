# NovaTech store database — `novatech_store.db` (SQLite)

All money is in Jordanian dinars (JOD). All dates are `YYYY-MM-DD` text.

## customers

| Column | Type | Notes |
|--------|------|-------|
| customer_id | TEXT | Primary key, e.g. `C001` |
| full_name | TEXT | |
| email | TEXT | |
| city | TEXT | Amman, Irbid, Zarqa, Salt, Madaba, Aqaba |
| joined_date | TEXT | |

## products

| Column | Type | Notes |
|--------|------|-------|
| product_id | TEXT | Primary key, e.g. `P01` |
| name | TEXT | |
| category | TEXT | Laptops, Phones, Tablets, Headphones, TVs, Wearables, Smart Home, Accessories |
| list_price_jod | REAL | Current list price |

## orders

| Column | Type | Notes |
|--------|------|-------|
| order_id | TEXT | Primary key, e.g. `NT-10560` |
| customer_id | TEXT | → customers |
| order_date | TEXT | |
| delivered_date | TEXT | NULL if not delivered |
| status | TEXT | `processing`, `shipped`, `delivered`, `cancelled`, `returned` |
| payment_method | TEXT | `card`, `cash_on_delivery`, `bank_transfer`, `pay_in_4` |
| total_jod | REAL | What the customer was charged |

## order_items

| Column | Type | Notes |
|--------|------|-------|
| order_id | TEXT | → orders |
| product_id | TEXT | → products |
| quantity | INTEGER | |
| unit_price_jod | REAL | Price actually charged per unit |

## returns

| Column | Type | Notes |
|--------|------|-------|
| order_id | TEXT | → orders (the whole order was returned) |
| return_date | TEXT | |
| reason | TEXT | |
