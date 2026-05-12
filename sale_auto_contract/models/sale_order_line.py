# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        orders = lines.mapped("order_id")
        if orders:
            orders._sync_auto_contract_lines()
        return lines

    def write(self, vals):
        res = super().write(vals)
        # Trigger re-sync whenever the product of an existing line changes,
        # because the linked contract products may have changed too.
        if "product_id" in vals:
            self.mapped("order_id")._sync_auto_contract_lines()
        return res

    def unlink(self):
        orders = self.mapped("order_id")
        res = super().unlink()
        if orders:
            orders.exists()._sync_auto_contract_lines()
        return res
