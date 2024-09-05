import logging
from datetime import datetime
from odoo import fields, models, api
_logger = logging.getLogger(__name__)
from odoo.tools.float_utils import json_float_round, float_compare
import requests


TAX_CODE_LETTERS = ['A', 'B', 'C', 'D', 'E']


def format_etims_datetime(dt):
    """ Format a UTC datetime as expected by eTIMS (only digits, Kenyan timezone). """
    return dt.replace(tzinfo=ZoneInfo('UTC')).astimezone(ZoneInfo('Africa/Nairobi')).strftime('%Y%m%d%H%M%S')


def parse_etims_datetime(dt_str):
    """ Parse a datetime string received from eTIMS into a UTC datetime. """
    return datetime.strptime(dt_str, '%Y%m%d%H%M%S').replace(tzinfo=ZoneInfo('Africa/Nairobi')).astimezone(ZoneInfo('UTC')).replace(tzinfo=None)

class PosOrder(models.Model):
    _name = 'pos.order'
    _inherit = ['pos.order', 'portal.mixin',]
    l10n_ke_payment_method_id = fields.Many2one(
        string="eTIMS Payment Method",
        comodel_name='l10n_ke_etims_vscu.code',
        domain=[('code_type', '=', '07')],
        help="Method of payment communicated to the KRA via eTIMS. This is required when confirming purchases.",
    )
    l10n_ke_reason_code_id = fields.Many2one(
        string="eTIMS Credit Note Reason",
        comodel_name='l10n_ke_etims_vscu.code',
        domain=[('code_type', '=', '32')],
        copy=False,
        help="Kenyan code for Credit Notes",
    )

    # === eTIMS Technical fields === #
    l10n_ke_oscu_confirmation_datetime = fields.Datetime(copy=False)
    l10n_ke_oscu_receipt_number = fields.Integer(string="Receipt Number", copy=False)
    l10n_ke_oscu_invoice_number = fields.Integer(string="Invoice Number", copy=False)
    l10n_ke_oscu_signature = fields.Char(string="eTIMS Signature", copy=False)
    l10n_ke_oscu_datetime = fields.Datetime(string="eTIMS Signing Time", copy=False)
    l10n_ke_oscu_internal_data = fields.Char(string="Internal Data", copy=False)
    l10n_ke_control_unit = fields.Char(string="Control Unit ID")


    def sign_order(self, order_data):
        order_id = order_data.get("name")
        orders = self.env["pos.order"].search([("pos_reference", "=", order_id)])
        for order in orders:
            lines = order.lines
            # TODO
            # 1. Check that all products in the order have a the required details to  generate etims code
            # 2. Check that the order has a payment method # Map Payment Method to eTIMS Payment Method
            json=order._l10n_ke_oscu_json_from_move()
            _logger.info('****json****')
            _logger.info(json)
        return False

    def _l10n_ke_oscu_json_from_move(self):
        """ Get the json content of the TrnsSalesSaveWr/TrnsPurchaseSave request from a move. """
        self.ensure_one()

        confirmation_datetime = format_etims_datetime(fields.Datetime.now())
        invoice_date = (self.invoice_date and self.invoice_date.strftime('%Y%m%d')) or ''
        original_invoice_number = (self.reversed_entry_id and self.reversed_entry_id.l10n_ke_oscu_invoice_number) or 0
        tax_details = self._prepare_invoice_aggregated_taxes()
        line_items = self._l10n_ke_oscu_get_json_from_lines(tax_details)

        tax_codes = {item['code']: item['tax_rate'] for item in
                     self.env['l10n_ke_etims_vscu.code'].search([('code_type', '=', '04')])}
        tax_rates = {f'taxRt{letter}': tax_codes.get(letter, 0) for letter in TAX_CODE_LETTERS}

        taxable_amounts = {
            f'taxblAmt{letter}': json_float_round(sum(
                item['taxblAmt'] for item in line_items if item['taxTyCd'] == letter
            ), 2) for letter in TAX_CODE_LETTERS
        }
        tax_amounts = {
            f'taxAmt{letter}': json_float_round(sum(
                item['taxAmt'] for item in line_items if item['taxTyCd'] == letter
            ), 2) for letter in TAX_CODE_LETTERS
        }

        content = {
            'invcNo': '',  # KRA Invoice Number (set at the point of sending)
            'trdInvcNo': (self.name or '')[:50],  # Trader system invoice number
            'orgInvcNo': original_invoice_number,  # Original invoice number
            'cfmDt': confirmation_datetime,  # Validated date
            'pmtTyCd': self.l10n_ke_payment_method_id.code or '',  # Payment type code
            'rcptTyCd': {  # Receipt code
                'out_invoice': 'S',  # - Sale
                'out_refund': 'R',  # - Credit note after sale
                'in_invoice': 'P',  # - Purchase
                'in_refund': 'R',  # - Credit note after purchase
            }[self.move_type],
            'salesTyCd': 'N',
            **taxable_amounts,
            **tax_amounts,
            **tax_rates,
            'totTaxblAmt': json_float_round(tax_details['base_amount'], 2),
            'totTaxAmt': json_float_round(tax_details['tax_amount'], 2),
            'totAmt': json_float_round(self.amount_total, 2),
            'totItemCnt': len(line_items),  # Total Item count
            'itemList': line_items,
            **self.company_id._l10n_ke_get_user_dict(self.create_uid, self.write_uid),
        }

        if self.is_purchase_document(include_receipts=True):
            content.update({
                'spplrTin': (self.partner_id.vat or '')[:11],  # Supplier VAT
                'spplrNm': (self.partner_id.name or '')[:60],  # Supplier name
                'regTyCd': 'M',  # Registration type code (Manual / Automatic)
                'pchsTyCd': 'N',  # Purchase type code (Copy / Normal / Proforma)
                'pchsSttsCd': '02',  # Transaction status code (02 approved / 05 credit note generated)
                'pchsDt': invoice_date,  # Purchase date
                # "spplrInvcNo": None,
            })
        else:
            receipt_part = {
                'custTin': (self.partner_id.vat or '')[:11],  # Partner VAT
                'rcptPbctDt': confirmation_datetime,  # Receipt published date
                'prchrAcptcYn': 'N',  # Purchase accepted Yes/No
            }
            if self.partner_id.mobile:
                receipt_part.update({
                    'custMblNo': (self.partner_id.mobile or '')[:20]  # Mobile number, not required
                })
            if self.partner_id.contact_address_inline:
                receipt_part.update({
                    'adrs': (self.partner_id.contact_address_inline or '')[:200],  # Address, not required
                })
            content.update({
                'custTin': (self.partner_id.vat or '')[:11],  # Partner VAT
                'custNm': (self.partner_id.name or '')[:60],  # Partner name
                'salesSttsCd': '02',  # Transaction status code (same as pchsSttsCd)
                'salesDt': invoice_date,  # Sales date
                'prchrAcptcYn': 'Y',
                'receipt': receipt_part,
            })
        if self.move_type in ('out_refund', 'in_refund'):
            content.update({'rfdRsnCd': self.l10n_ke_reason_code_id.code})
        return content

    def _l10n_ke_oscu_get_json_from_lines(self, tax_details):
        """ Return the values that should be sent to eTIMS for the lines in self. """
        self.ensure_one()
        lines_values = []
        for index, line in enumerate(
                self.invoice_line_ids.filtered(lambda l: l.display_type not in ('line_section', 'line_note'))):
            product = line.product_id  # for ease of reference
            product_uom_qty = line.product_uom_id._compute_quantity(line.quantity, product.uom_id)

            line_tax_details = next(
                line_tax_details
                for tax_grouping_key, line_tax_details in
                tax_details['tax_details_per_record'][line]['tax_details'].items()
                if tax_grouping_key['tax'].l10n_ke_tax_type_id  # We only want to report VAT taxes
            )

            if line.quantity and line.discount != 100:
                # By computing the price_unit this way, we ensure that we get the price before the VAT tax, regardless of what
                # other price_include / price_exclude taxes are defined on the product.
                price_subtotal_before_discount = line_tax_details['base_amount'] / (1 - (line.discount / 100))
                price_unit = price_subtotal_before_discount / line.quantity
            else:
                price_unit = line.price_unit
                price_subtotal_before_discount = price_unit * line.quantity
            discount_amount = price_subtotal_before_discount - line_tax_details['base_amount']

            line_values = {
                'itemSeq': index + 1,  # Line number
                'itemCd': product.l10n_ke_item_code,  # Item code as defined by us, of the form KE2BFTNE0000000000000039
                'itemClsCd': product.unspsc_code_id.code,  # Item classification code, in this case the UNSPSC code
                'itemNm': line.name,  # Item name
                'pkgUnitCd': product.l10n_ke_packaging_unit_id.code,
                # Packaging code, describes the type of package used
                'pkg': product_uom_qty / product.l10n_ke_packaging_quantity,  # Number of packages used
                'qtyUnitCd': line.product_uom_id.l10n_ke_quantity_unit_id.code,
                # The UOMs as defined by the KRA, defined seperately from the UOMs on the line
                'qty': line.quantity,
                'prc': price_unit,
                'splyAmt': price_subtotal_before_discount,
                'dcRt': line.discount,
                'dcAmt': discount_amount,
                'taxTyCd': line_tax_details['tax'].l10n_ke_tax_type_id.code,
                'taxblAmt': line_tax_details['base_amount'],
                'taxAmt': line_tax_details['tax_amount'],
                'totAmt': line_tax_details['base_amount'] + line_tax_details['tax_amount'],
            }

            fields_to_round = ('pkg', 'qty', 'prc', 'splyAmt', 'dcRt', 'dcAmt', 'taxblAmt', 'taxAmt', 'totAmt')
            for field in fields_to_round:
                line_values[field] = json_float_round(line_values[field], 2)

            if product.barcode:
                line_values.update({'bcd': product.barcode})

            lines_values.append(line_values)
        return lines_values