# Sale Auto Contract

Automatically generate a recurring contract (yearly) upon sale order
confirmation, based on "contract products" linked to the sold products.

## Features

- On a product, configure one or more **Contract Products** (tab "Contract
  Products"). These are the items that will end up on the recurring contract
  when the product is sold.
- On a quotation, a **Contract Products** tab shows the lines that will be
  used to build the contract. Prices are editable per customer.
- A **Contract Preview** button opens a read-only preview of the contract
  that would be generated — without creating it.
- When the quotation is sent by email, a **PDF draft of the contract** is
  automatically attached alongside the quotation PDF.
- On sale order confirmation, a `contract.contract` record is created
  automatically with:
  - yearly recurrence (`recurring_rule_type = 'yearly'`, `recurring_interval = 1`)
  - pre-paid invoicing
  - one line per contract-product spec recorded on the quotation
- The sold products themselves are **not** added to the contract; only the
  linked contract products are.
- A smart button on the sale order shows the generated contract(s).

## Price editing and sync behavior

Contract-product lines are auto-populated on the quotation from the linked
contract products. The salesperson can edit **unit price, quantity and
description**.

When the quotation lines change:
- **New** (source order line, contract product) pairs are added.
- Pairs no longer present are removed **only if they were not manually
  edited**. Edited lines (flag `manually_edited=True`) are preserved.
- A **Refresh from quotation** button on the tab triggers the same logic
  manually.

## PDF draft generation — technical note

The contract draft PDF is rendered by temporarily creating the contract in a
Postgres savepoint, rendering `contract.report_contract`, then rolling back
the savepoint. Nothing is persisted in the database.

## Dependencies

- `sale_management` (core)
- `contract` (OCA, branch 18.0)

## Usage

1. Install the OCA `contract` module.
2. Install `sale_auto_contract`.
3. On a product (e.g. "Software Licence X"), go to the "Contract Products" tab
   and add the products that represent the recurring services (e.g.
   "Annual Maintenance X", "Hosting X").
4. Create a quotation with the parent product.
5. Go to the **Contract Products** tab on the quotation and adjust the unit
   prices for this specific customer.
6. Click **Contract Preview** to preview the contract, or **Send by Email**
   to send the quotation together with the contract draft PDF.
7. Confirm the quotation: the contract is created automatically and linked
   to the sale order via a smart button.

## License

AGPL-3.0-or-later.
