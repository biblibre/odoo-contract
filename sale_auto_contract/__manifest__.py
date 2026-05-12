# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "Sale Auto Contract",
    "summary": "Automatically generate a recurring contract upon sale order "
               "confirmation, based on contract products linked to the sold "
               "products.",
    "version": "18.0.1.1.0",
    "category": "Sales",
    "author": "AFI",
    "website": "https://www.example.com",
    "license": "AGPL-3",
    "depends": [
        "sale_management",
        "contract",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/product_template_views.xml",
        "views/sale_order_views.xml",
        "views/contract_preview_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
