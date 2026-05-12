# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class ContractContract(models.Model):
    _inherit = "contract.contract"

    sale_auto_contract_origin_id = fields.Many2one(
        comodel_name="sale.order",
        string="Originating Sale Order",
        index=True,
        readonly=True,
        copy=False,
        help="The sale order that triggered the automatic creation of this "
             "contract.",
    )
