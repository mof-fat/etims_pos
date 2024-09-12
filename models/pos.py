import logging
from datetime import datetime
from odoo import fields, models, api, _
_logger = logging.getLogger(__name__)
from odoo.tools import float_is_zero, float_round, float_repr, float_compare
import requests
from zoneinfo import ZoneInfo
from odoo.exceptions import ValidationError, UserError
import pytz
import json
from typing import Any, Union


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

    def json_float_round(self, data: Any, decimal_places: int) -> Any:
        """
        Recursively rounds all floating-point numbers in a JSON-serializable object to a specified number of decimal places.

        :param data: JSON-serializable object (dict, list, or primitive).
        :param decimal_places: Number of decimal places to round floating-point numbers to.
        :return: JSON-serializable object with rounded floating-point numbers.
        """
        if isinstance(data, dict):
            return {key: json_float_round(value, decimal_places) for key, value in data.items()}
        elif isinstance(data, list):
            return [json_float_round(item, decimal_places) for item in data]
        elif isinstance(data, float):
            return round(data, decimal_places)
        else:
            return data

    def action_pos_order_paid(self):
        self.ensure_one()

        # TODO: add support for mix of cash and non-cash payments when both cash_rounding and only_round_cash_method are True
        if not self.config_id.cash_rounding \
                or self.config_id.only_round_cash_method \
                and not any(p.payment_method_id.is_cash_count for p in self.payment_ids):
            total = self.amount_total
        else:
            total = float_round(self.amount_total, precision_rounding=self.config_id.rounding_method.rounding,
                                rounding_method=self.config_id.rounding_method.rounding_method)

        isPaid = float_is_zero(total - self.amount_paid, precision_rounding=self.currency_id.rounding)

        if not isPaid and not self.config_id.cash_rounding:
            raise UserError(_("Order %s is not fully paid.", self.name))
        elif not isPaid and self.config_id.cash_rounding:
            currency = self.currency_id
            if self.config_id.rounding_method.rounding_method == "HALF-UP":
                maxDiff = currency.round(self.config_id.rounding_method.rounding / 2)
            else:
                maxDiff = currency.round(self.config_id.rounding_method.rounding)

            diff = currency.round(self.amount_total - self.amount_paid)
            if not abs(diff) <= maxDiff:
                raise UserError(_("Order %s is not fully paid.", self.name))

        self.write({'state': 'paid'})
        lines = self.lines
        self.sign_order(lines)
        return True


    def sign_order(self, lines):
            # TODO
            # 1. Check that all products in the order have a the required details to  generate etims code
            # 2. Check that the order has a payment method # Map Payment Method to eTIMS Payment Method

            order = self

            _logger.info(f'==================SIGN_ORDER==================== {order.pos_reference}')

            # 1
            for line in lines:
                _logger.info(f'==ORDER=={order.pos_reference}')
                _logger.info(f'==ORDER_DATE=={order.date_order}')
                _logger.info(f'==ORDER_AMOUNT_PAID=={order.amount_paid}')
                _logger.info(f'==ORDER_TAX_AMOUNT=={order.amount_tax}')
                _logger.info(f'==ORDER_PAYMENT_METHOD=={order.payment_ids.payment_method_id.name}')
                _logger.info(f'==CUSTOMER=={order.partner_id.name}')
                _logger.info(f'==PRODUCT=={line.product_id.name}')
                _logger.info(f'==LINE_PRICE=={line.price_unit}')
                _logger.info(f'==LINE_QTY=={line.qty}')
                _logger.info(f'==LINE_TAX_IDS=={line.tax_ids}')
                _logger.info(f'==LINE_TAX_FISCAL=={line.tax_ids_after_fiscal_position}')
                _logger.info(f'==LINE_UOM=={line.product_uom_id.name}')
                _logger.info('')

            json=self._l10n_ke_oscu_json_from_move(order)
            _logger.info('***************json***************')
            _logger.info(json)

    def _l10n_ke_oscu_json_from_move(self, order):
        """ Get the json content of the TrnsSalesSaveWr/TrnsPurchaseSave request from a move. """
        self.ensure_one()

        confirmation_datetime = format_etims_datetime(fields.Datetime.now())

        invoice_date = order.date_order or ''
        _logger.info(f'=============INVOICE_DATE========== {invoice_date}')

        original_invoice_number = order.pos_reference or 0
        _logger.info(f'===========INVOICE_NUMBER========= {original_invoice_number}')

        tax_codes = {item['code']: item['tax_rate'] for item in
                     self.env['l10n_ke_etims_vscu.code'].search([('code_type', '=', '04')])}
        _logger.info(f'========TAX_CODES========== {tax_codes}')

        tax_rates = {f'taxRt{letter}': tax_codes.get(letter, 0) for letter in TAX_CODE_LETTERS}
        _logger.info(f'========TAX_RATES========== {tax_rates}')

        line_items = self._l10n_ke_oscu_get_json_from_lines(order)
        _logger.info(f'========LINE_ITEMS========== {line_items}')

        taxable_amounts = {
            f'taxblAmt{letter}': self.json_float_round(sum(
                item['taxblAmt'] for item in line_items if item['taxTyCd'] == letter
            ), 2) for letter in TAX_CODE_LETTERS
        }
        _logger.info(f'========TAXABLE_AMOUNTS========== {taxable_amounts}')

        tax_amounts = {
            f'taxAmt{letter}': self.json_float_round(sum(
                item['taxAmt'] for item in line_items if item['taxTyCd'] == letter
            ), 2) for letter in TAX_CODE_LETTERS
        }
        _logger.info(f'========TAX_AMOUNTS========== {tax_amounts}')

        content = {
            'invcNo': order.pos_reference,  # KRA Invoice Number (set at the point of sending)
            'trdInvcNo': (order.pos_reference or '')[:50],  # Trader system invoice number
            'orgInvcNo': original_invoice_number,  # Original invoice number
            'cfmDt': confirmation_datetime,  # Validated date
            'pmtTyCd': '',  # Payment type code
            'rcptTyCd': "S",
            'salesTyCd': 'N',
            **taxable_amounts,
            **tax_amounts,
            **tax_rates,
            'totTaxblAmt': self.json_float_round(order.amount_total, 2),
            'totTaxAmt': self.json_float_round(order.amount_tax, 2),
            'totAmt': self.json_float_round(order.amount_total, 2),
            'totItemCnt': len(line_items),  # Total Item count
            'itemList': line_items,
            **self.company_id._l10n_ke_get_user_dict(self.create_uid, self.write_uid),
        }

        # if self.is_purchase_document(include_receipts=True):
        #     content.update({
        #         'spplrTin': (self.partner_id.vat or '')[:11],  # Supplier VAT
        #         'spplrNm': (self.partner_id.name or '')[:60],  # Supplier name
        #         'regTyCd': 'M',  # Registration type code (Manual / Automatic)
        #         'pchsTyCd': 'N',  # Purchase type code (Copy / Normal / Proforma)
        #         'pchsSttsCd': '02',  # Transaction status code (02 approved / 05 credit note generated)
        #         'pchsDt': invoice_date,  # Purchase date
        #         # "spplrInvcNo": None,
        #     })
        # else:

        receipt_part = {
            'custTin': (order.partner_id.vat or '')[:11],  # Partner VAT
            'rcptPbctDt': confirmation_datetime,  # Receipt published date
            'prchrAcptcYn': 'N',  # Purchase accepted Yes/No
        }
        if order.partner_id.mobile:
            receipt_part.update({
                'custMblNo': (order.partner_id.mobile or '')[:20]  # Mobile number, not required
            })
        if order.partner_id.contact_address_inline:
            receipt_part.update({
                'adrs': (order.partner_id.contact_address_inline or '')[:200],  # Address, not required
            })
        content.update({
            'custTin': (order.partner_id.vat or '')[:11],  # Partner VAT
            'custNm': (order.partner_id.name or '')[:60],  # Partner name
            'salesSttsCd': '02',  # Transaction status code (same as pchsSttsCd)
            'salesDt': invoice_date,  # Sales date
            'prchrAcptcYn': 'Y',
            'receipt': receipt_part,
        })

        # if self.move_type in ('out_refund', 'in_refund'):
        #     content.update({'rfdRsnCd': self.l10n_ke_reason_code_id.code})
        return content

    def _l10n_ke_oscu_get_json_from_lines(self, order):
        """ Return the values that should be sent to eTIMS for the lines in self. """
        self.ensure_one()
        lines_values = []
        for index, line in enumerate(order.lines):

            product = line.product_id  # for ease of reference
            product_uom_qty = line.product_uom_id._compute_quantity(line.qty, product.uom_id)

            if line.qty and line.discount != 100:
                # By computing the price_unit this way, we ensure that we get the price before the VAT tax, regardless of what
                # other price_include / price_exclude taxes are defined on the product.
                price_subtotal_before_discount = line.price_subtotal / (1 - (line.discount / 100))
                price_unit = price_subtotal_before_discount / line.qty
            else:
                price_unit = line.price_unit
                price_subtotal_before_discount = price_unit * line.qty
            discount_amount = price_subtotal_before_discount - line.price_subtotal

            line_values = {
                'itemSeq': index + 1,  # Line number
                'itemCd': product.l10n_ke_item_code,  # Item code as defined by us, of the form KE2BFTNE0000000000000039
                'itemClsCd': product.unspsc_code_id.code,  # Item classification code, in this case the UNSPSC code
                'itemNm': line.product_id.name,  # Item name
                'pkgUnitCd': product.l10n_ke_packaging_unit_id.code,
                # Packaging code, describes the type of package used
                'pkg': product_uom_qty / product.l10n_ke_packaging_quantity,  # Number of packages used
                'qtyUnitCd': line.product_uom_id.l10n_ke_quantity_unit_id.code,
                # The UOMs as defined by the KRA, defined seperately from the UOMs on the line
                'qty': line.qty,
                'prc': price_unit,
                'splyAmt': price_subtotal_before_discount,
                'dcRt': line.discount,
                'dcAmt': discount_amount,
                'taxTyCd': '',
                'taxblAmt': line.price_subtotal,
                'taxAmt': line.price_subtotal_incl - line.price_subtotal,
                'totAmt': line.price_subtotal_incl,
            }

            fields_to_round = ('pkg', 'qty', 'prc', 'splyAmt', 'dcRt', 'dcAmt', 'taxblAmt', 'taxAmt', 'totAmt')
            for field in fields_to_round:
                line_values[field] = self.json_float_round(line_values[field], 2)

            if product.barcode:
                line_values.update({'bcd': product.barcode})

            lines_values.append(line_values)
        return lines_values