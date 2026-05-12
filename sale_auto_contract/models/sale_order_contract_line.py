# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class SaleOrderContractLine(models.Model):
    _name = "sale.order.contract.line"
    _description = "Sale Order Contract Line (spec for the contract to create)"
    _order = "sequence, id"

    order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Sale Order",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    source_order_line_id = fields.Many2one(
        comodel_name="sale.order.line",
        string="Source Quotation Line",
        ondelete="set null",
        help="The quotation line whose product is linked to this contract "
             "product. May be lost if the source line is deleted; the "
             "contract line is then kept but orphaned.",
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Contract Product",
        required=True,
    )
    name = fields.Char(
        string="Description",
        compute="_compute_name",
        store=True,
        readonly=False,
    )
    quantity = fields.Float(string="Quantity", default=1.0, required=True)
    uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="UoM",
        compute="_compute_uom_id",
        store=True,
        readonly=False,
    )
    price_unit = fields.Float(
        string="Unit Price",
        compute="_compute_price_unit",
        store=True,
        readonly=False,
        help="Editable by the salesperson. Defaults to the product list price "
             "on creation.",
    )
    currency_id = fields.Many2one(
        related="order_id.currency_id", readonly=True,
    )
    subtotal = fields.Monetary(
        string="Subtotal",
        compute="_compute_subtotal",
        currency_field="currency_id",
    )
    manually_edited = fields.Boolean(
        string="Manually Edited",
        default=False,
        help="Technical flag: set to True when the user changes the price, "
             "quantity or description manually, to preserve the edits when "
             "the quotation lines are modified.",
    )

    @api.depends("product_id")
    def _compute_name(self):
        for line in self:
            if not line.name and line.product_id:
                line.name = line.product_id.display_name

    @api.depends("product_id")
    def _compute_uom_id(self):
        for line in self:
            if not line.uom_id and line.product_id:
                line.uom_id = line.product_id.uom_id

    @api.depends("product_id")
    def _compute_price_unit(self):
        for line in self:
            if not line.manually_edited and line.product_id:
                line.price_unit = line.product_id.lst_price

    @api.depends("quantity", "price_unit")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit

    def write(self, vals):
        # Any manual change to price/qty/name marks the line as edited
        tracked = {"price_unit", "quantity", "name"}
        if tracked.intersection(vals.keys()) and not self.env.context.get(
            "sale_auto_contract_sync"
        ):
            vals.setdefault("manually_edited", True)
        return super().write(vals)
