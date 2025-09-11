# Offer Management Module

This module handles the creation of sales offers for your products and provides a template for automating the process of publishing them to the Best Buy marketplace. An "offer" connects a specific product variant (identified by its SKU) from your catalog to a price and a stock quantity.

## File Structure

*   `manage_offers.py`: A command-line script to create and view your sales offers.
*   `offers.json`: The database file that stores a list of all your currently defined offers.
*   `publish_offers.py`: A Playwright script that serves as a **template** for automating the process of logging into the Best Buy seller portal and publishing the offers from `offers.json`.

## How to Use `manage_offers.py`

This script allows you to manage the `offers.json` file.

### 1. Create or Update an Offer

To create a new offer or update an existing one, use the `create` command. You must provide a SKU that already exists in your `catalog/products.json` file. If you provide a SKU that is already in `offers.json`, its price and stock will be updated.

**Example:**
```bash
python3 offers/manage_offers.py create \
--sku "FB-SLX1-16-512-GR" \
--price 1499.99 \
--stock 25
```
This will create an offer for the specified SKU with a price of $1499.99 and a stock level of 25.

### 2. View All Offers

To see all the offers you have created, use the `view` command.

```bash
python3 offers/manage_offers.py view
```

## How to Use `publish_offers.py`

This script is a **template** designed to get you started with automating offer publishing. Because every website is different and can change over time, you will need to finalize the script yourself.

### Step 1: Add Your Credentials

Before running the script, you must add your Best Buy seller portal login details to the `secrets.txt` file in the root directory.

Open `secrets.txt` and replace the placeholder values for:
*   `BEST_BUY_USERNAME`
*   `BEST_BUY_PASSWORD`

### Step 2: Customize the Playwright Selectors

The script needs to know how to find the username field, password field, and login button on the Best Buy portal. The current values in the script are **guesses**. You must replace them with the correct ones.

**How to find the correct selectors:**
1.  Open the seller portal login page in your web browser (e.g., Chrome, Firefox).
2.  Right-click on the username input box and select **"Inspect"** or **"Inspect Element"**. This will open the developer tools.
3.  In the developer tools, you will see the HTML code for the input field. Look for a unique attribute like `id`, `name`, or `data-testid`. For example, you might see `<input id="login_user_name" name="user_name">`.
4.  Choose one unique attribute to create your selector. A `name` selector looks like `input[name="user_name"]`. An `id` selector looks like `#login_user_name`.
5.  Open `publish_offers.py` and replace the placeholder selector in the `page.locator()` function with the one you found.
6.  Repeat this process for the password field and the login button.

### Step 3: Implement the Offer Publishing Logic

The script will successfully log you in after you've configured the selectors. The final part is to implement the loop that creates the offers on the website. The script has a commented-out `for` loop with instructions and examples on how to:
*   Navigate to the correct page for managing offers.
*   Search for an existing offer by SKU.
*   Fill in the price and quantity fields.
*   Save the changes.

You will need to follow the same process of inspecting the website to find the selectors for these elements and complete the script.
