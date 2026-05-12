# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    contract_product_ids = fields.Many2many(
        comodel_name="product.product",
        relation="product_template_contract_product_rel",
        column1="product_tmpl_id",
        column2="contract_product_id",
        string="Contract Products",
        help="When this product is added to a confirmed sale order, the "
             "listed products here will be added as lines of the generated "
             "contract. The product itself is NOT added to the contract.",
    )
    has_contract_products = fields.Boolean(
        string="Has Contract Products",
        compute="_compute_has_contract_products",
        store=True,
    )

    def _compute_has_contract_products(self):
        for tmpl in self:
            tmpl.has_contract_products = bool(tmpl.contract_product_ids)
