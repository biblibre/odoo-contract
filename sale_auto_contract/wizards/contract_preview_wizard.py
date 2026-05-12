# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _, api, fields, models


class ContractPreviewWizard(models.TransientModel):
    _name = "sale.auto.contract.preview"
    _description = "Contract Preview from Sale Order"

    sale_order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Sale Order",
        required=True,
        readonly=True,
    )
    name = fields.Char(string="Contract Name", readonly=True)
    partner_id = fields.Many2one(
        comodel_name="res.partner", string="Customer", readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company", string="Company", readonly=True,
    )
    pricelist_id = fields.Many2one(
        comodel_name="product.pricelist", string="Pricelist", readonly=True,
    )
    date_start = fields.Date(string="Start Date", readonly=True)
    recurring_rule_type = fields.Char(string="Recurrence", readonly=True)
    recurring_interval = fields.Integer(string="Every", readonly=True)
    recurring_invoicing_type = fields.Char(
        string="Invoicing Type", readonly=True,
    )
    line_ids = fields.One2many(
        comodel_name="sale.auto.contract.preview.line",
        inverse_name="wizard_id",
        string="Preview Lines",
        readonly=True,
    )
    total_amount = fields.Monetary(
        string="Total (per period)",
        compute="_compute_total_amount",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        compute="_compute_currency_id",
    )

    @api.depends("line_ids.subtotal")
    def _compute_total_amount(self):
        for wiz in self:
            wiz.total_amount = sum(wiz.line_ids.mapped("subtotal"))

    @api.depends("sale_order_id")
    def _compute_currency_id(self):
        for wiz in self:
            wiz.currency_id = wiz.sale_order_id.currency_id

    def _populate_from_order(self):
        self.ensure_one()
        order = self.sale_order_id
        payload = order._build_contract_payload()
        header = payload["header"]
        self.write({
            "name": header.get("name"),
            "partner_id": header.get("partner_id"),
            "company_id": header.get("company_id"),
            "pricelist_id": header.get("pricelist_id") or False,
            "date_start": header.get("date_start"),
            "recurring_rule_type": header.get("recurring_rule_type"),
            "recurring_interval": header.get("recurring_interval"),
            "recurring_invoicing_type": header.get("recurring_invoicing_type"),
        })
        # Clear any pre-existing lines and refill
        self.line_ids.unlink()
        line_model = self.env["sale.auto.contract.preview.line"]
        for line_vals in payload["lines"]:
            line_model.create({
                "wizard_id": self.id,
                "product_id": line_vals["product_id"],
                "name": line_vals["name"],
                "quantity": line_vals["quantity"],
                "uom_id": line_vals["uom_id"],
                "price_unit": line_vals["price_unit"],
            })

    def action_confirm_order(self):
        """Close the wizard; the user can click on Confirm on the SO afterwards.
        (Kept as hook / future extension point.)
        """
        self.ensure_one()
        return {"type": "ir.actions.act_window_close"}


class ContractPreviewWizardLine(models.TransientModel):
    _name = "sale.auto.contract.preview.line"
    _description = "Contract Preview Line"

    wizard_id = fields.Many2one(
        comodel_name="sale.auto.contract.preview",
        required=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one(
        comodel_name="product.product", string="Product", readonly=True,
    )
    name = fields.Char(string="Description", readonly=True)
    quantity = fields.Float(string="Quantity", readonly=True)
    uom_id = fields.Many2one(
        comodel_name="uom.uom", string="Unit of Measure", readonly=True,
    )
    price_unit = fields.Float(string="Unit Price", readonly=True)
    currency_id = fields.Many2one(
        related="wizard_id.currency_id", readonly=True,
    )
    subtotal = fields.Monetary(
        string="Subtotal",
        compute="_compute_subtotal",
        currency_field="currency_id",
    )

    @api.depends("quantity", "price_unit")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit
