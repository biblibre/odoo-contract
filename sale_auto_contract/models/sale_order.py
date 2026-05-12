# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import base64
import logging

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

CONTRACT_REPORT_XML_ID = "contract.report_contract"


class SaleOrder(models.Model):
    _inherit = "sale.order"

    auto_contract_line_ids = fields.One2many(
        comodel_name="sale.order.contract.line",
        inverse_name="order_id",
        string="Contract Products (preview)",
        copy=True,
        help="Lines that will be used to build the recurring contract upon "
             "confirmation. Automatically populated from the contract "
             "products linked to the order line products. Salespeople can "
             "edit the unit price per customer.",
    )
    auto_contract_ids = fields.One2many(
        comodel_name="contract.contract",
        inverse_name="sale_auto_contract_origin_id",
        string="Generated Contracts",
        readonly=True,
        copy=False,
    )
    auto_contract_count = fields.Integer(
        compute="_compute_auto_contract_count",
    )
    has_contract_products_in_lines = fields.Boolean(
        compute="_compute_has_contract_products_in_lines",
        help="Technical flag: True if any order line product has contract "
             "products configured.",
    )

    def _compute_auto_contract_count(self):
        for order in self:
            order.auto_contract_count = len(order.auto_contract_ids)

    @api.depends(
        "order_line.product_id",
        "order_line.product_id.product_tmpl_id.contract_product_ids",
    )
    def _compute_has_contract_products_in_lines(self):
        for order in self:
            order.has_contract_products_in_lines = any(
                line.product_id.product_tmpl_id.contract_product_ids
                for line in order.order_line
                if line.product_id and not line.display_type
            )

    # ------------------------------------------------------------------
    # Synchronisation order_line <-> auto_contract_line_ids
    # ------------------------------------------------------------------

    def _sync_auto_contract_lines(self):
        """Add contract-product lines for new source lines, remove those
        whose (source, product) pair is no longer present AND that were not
        manually edited. Existing manually edited lines are preserved.
        """
        ContractLine = self.env["sale.order.contract.line"]
        for order in self:
            existing = order.auto_contract_line_ids
            existing_keys = {
                (line.source_order_line_id.id, line.product_id.id): line
                for line in existing
            }
            expected_keys = set()
            to_create = []
            for ol in order.order_line:
                if ol.display_type or not ol.product_id:
                    continue
                linked = ol.product_id.product_tmpl_id.contract_product_ids
                for cp in linked:
                    key = (ol.id, cp.id)
                    expected_keys.add(key)
                    if key not in existing_keys:
                        to_create.append({
                            "order_id": order.id,
                            "source_order_line_id": ol.id,
                            "product_id": cp.id,
                        })
            if to_create:
                ContractLine.with_context(
                    sale_auto_contract_sync=True
                ).create(to_create)
            to_unlink = ContractLine
            for key, line in existing_keys.items():
                if key not in expected_keys and not line.manually_edited:
                    to_unlink |= line
            if to_unlink:
                to_unlink.unlink()

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._sync_auto_contract_lines()
        return orders

    def write(self, vals):
        res = super().write(vals)
        if "order_line" in vals:
            self._sync_auto_contract_lines()
        return res

    def action_sync_auto_contract_lines(self):
        """Manual recompute button — keeps user edits on price/quantity."""
        self._sync_auto_contract_lines()
        return True

    # ------------------------------------------------------------------
    # Contract building helpers (from auto_contract_line_ids)
    # ------------------------------------------------------------------

    def _prepare_contract_vals(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        return {
            "name": _("Contract for %s") % self.name,
            "partner_id": self.partner_id.id,
            "company_id": self.company_id.id,
            "pricelist_id": self.pricelist_id.id or False,
            "payment_term_id": self.payment_term_id.id or False,
            "date_start": today,
            "recurring_rule_type": "yearly",
            "recurring_interval": 1,
            "recurring_invoicing_type": "pre-paid",
            "contract_type": "sale",
            "sale_auto_contract_origin_id": self.id,
        }

    def _prepare_contract_line_vals_from_spec(self, spec_line):
        today = fields.Date.context_today(self)
        return {
            "product_id": spec_line.product_id.id,
            "name": spec_line.name or spec_line.product_id.display_name,
            "quantity": spec_line.quantity,
            "uom_id": spec_line.uom_id.id or spec_line.product_id.uom_id.id,
            "price_unit": spec_line.price_unit,
            "date_start": today,
            "recurring_next_date": today,
            "recurring_rule_type": "yearly",
            "recurring_interval": 1,
            "recurring_invoicing_type": "pre-paid",
        }

    def _build_contract_payload(self):
        self.ensure_one()
        header = self._prepare_contract_vals()
        lines = [
            self._prepare_contract_line_vals_from_spec(sl)
            for sl in self.auto_contract_line_ids
        ]
        return {"header": header, "lines": lines}

    # ------------------------------------------------------------------
    # Contract creation on confirmation
    # ------------------------------------------------------------------

    def _create_auto_contract(self):
        self.ensure_one()
        payload = self._build_contract_payload()
        if not payload["lines"]:
            return self.env["contract.contract"]
        vals = dict(payload["header"])
        vals["contract_line_ids"] = [
            (0, 0, line_vals) for line_vals in payload["lines"]
        ]
        contract = self.env["contract.contract"].create(vals)
        self.message_post(
            body=Markup("%s %s") % (
                _("Contract generated from this quotation:"),
                contract._get_html_link(),
            )
        )
        return contract

    def action_confirm(self):
        res = super().action_confirm()
        for order in self:
            if order.auto_contract_ids:
                continue
            try:
                order._create_auto_contract()
            except Exception as exc:  # pragma: no cover
                _logger.exception(
                    "Failed to auto-generate contract for sale order %s: %s",
                    order.name, exc,
                )
                raise
        return res

    # ------------------------------------------------------------------
    # Draft PDF generation for email attachment
    # ------------------------------------------------------------------

    def _render_contract_draft_pdf(self):
        """Render the contract draft PDF without persisting the contract.

        Uses a savepoint + rollback strategy so nothing is ever committed to
        the database. Returns (pdf_bytes, filename) or (None, None) if there
        is nothing to render.
        """
        self.ensure_one()
        payload = self._build_contract_payload()
        if not payload["lines"]:
            return None, None

        savepoint_name = f"sale_auto_contract_draft_{self.id}"
        cr = self.env.cr
        cr.execute(f'SAVEPOINT "{savepoint_name}"')
        try:
            vals = dict(payload["header"])
            vals["contract_line_ids"] = [
                (0, 0, line_vals) for line_vals in payload["lines"]
            ]
            draft = self.env["contract.contract"].create(vals)
            self.env.flush_all()
            pdf_bytes, _content_type = (
                self.env["ir.actions.report"]
                ._render_qweb_pdf(CONTRACT_REPORT_XML_ID, draft.ids)
            )
            filename = _("Contract draft - %s.pdf") % self.name
            return pdf_bytes, filename
        finally:
            cr.execute(f'ROLLBACK TO SAVEPOINT "{savepoint_name}"')
            self.env.invalidate_all()

    def _create_contract_draft_attachment(self):
        """Render the PDF and return an ir.attachment recordset (or empty)."""
        self.ensure_one()
        pdf_bytes, filename = self._render_contract_draft_pdf()
        if not pdf_bytes:
            return self.env["ir.attachment"]
        attachment = self.env["ir.attachment"].create({
            "name": filename,
            "type": "binary",
            "datas": base64.b64encode(pdf_bytes),
            "res_model": "sale.order",
            "res_id": self.id,
            "mimetype": "application/pdf",
        })
        return attachment

    # ------------------------------------------------------------------
    # Override Send by Email to attach the contract draft PDF
    # ------------------------------------------------------------------

    def action_quotation_send(self):
        action = super().action_quotation_send()
        if not isinstance(action, dict):
            return action
        ctx = dict(action.get("context") or {})
        for order in self:
            if not order.auto_contract_line_ids:
                continue
            try:
                attachment = order._create_contract_draft_attachment()
            except Exception as exc:
                _logger.exception(
                    "Could not render contract draft PDF for %s: %s",
                    order.name, exc,
                )
                continue
            if attachment:
                existing = list(ctx.get("default_attachment_ids") or [])
                existing.append((4, attachment.id))
                ctx["default_attachment_ids"] = existing
        action["context"] = ctx
        return action

    # ------------------------------------------------------------------
    # Preview wizard action (unchanged API)
    # ------------------------------------------------------------------

    def action_preview_auto_contract(self):
        self.ensure_one()
        if not self.auto_contract_line_ids:
            raise UserError(_(
                "None of the products in this quotation are linked to "
                "contract products. Nothing to preview."
            ))
        wizard = self.env["sale.auto.contract.preview"].create({
            "sale_order_id": self.id,
        })
        wizard._populate_from_order()
        return {
            "type": "ir.actions.act_window",
            "name": _("Contract Preview"),
            "res_model": "sale.auto.contract.preview",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_view_auto_contracts(self):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": _("Generated Contracts"),
            "res_model": "contract.contract",
        }
        if len(self.auto_contract_ids) == 1:
            action.update({
                "view_mode": "form",
                "res_id": self.auto_contract_ids.id,
            })
        else:
            action.update({
                "view_mode": "list,form",
                "domain": [("id", "in", self.auto_contract_ids.ids)],
            })
        return action
