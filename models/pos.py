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
from psycopg2.errors import LockNotAvailable
import pyqrcode as pyqrcode
import io
import base64


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
    l10n_ke_qr_code = fields.Char('QR Code')
    l10n_ke_pmtTyCd = fields.Char(string="PMT TyCd")

    @api.depends('lines.price_unit', 'lines.qty')
    def compute_total_before_discount(self):
        lines = self.lines
        for line in lines:
            price_after_discount = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            subtotal_after_discount = price_after_discount * line.qty

            _logger.info(f'===============SUB_DISCOUNT============= %s', subtotal_after_discount)

    def json_float_round(self, data: Any, decimal_places: int) -> Any:
        """
        Recursively rounds all floating-point numbers in a JSON-serializable object to a specified number of decimal places.

        :param data: JSON-serializable object (dict, list, or primitive).
        :param decimal_places: Number of decimal places to round floating-point numbers to.
        :return: JSON-serializable object with rounded floating-point numbers.
        """
        if isinstance(data, dict):
            return {key: self.json_float_round(value, decimal_places) for key, value in data.items()}
        elif isinstance(data, list):
            return [self.json_float_round(item, decimal_places) for item in data]
        elif isinstance(data, float):
            return round(data, decimal_places)
        else:
            return data

    def sign_order(self, order):
        # TODO
        # 1. Check that all products in the order have a the required details to  generate etims code
        # 2. Check that the order has a payment method # Map Payment Method to eTIMS Payment Method

        payment_id = order['statement_ids'][0][2]['payment_method_id']
        payment_code = self.env['pos.payment'].search([('id', '=', payment_id)])

        if (
                payment_code
                and payment_code.payment_method_id
                and payment_code.payment_method_id.l10n_ke_payment_method_id
        ):
            payment_method = payment_code.payment_method_id.l10n_ke_payment_method_id
            if not payment_method.code:
                order['pmtTyCd'] = ""
                return order
            else:
                order['pmtTyCd'] = payment_method.code


        send_pos_order = {}
        order_ = self.env['pos.order'].search([('pos_reference', '=', order['name'])])
        lines = order_.lines
        _logger.info(f'=============ORDER_1============{order_}')

        if order_:
            # 1
            for line in lines:
                _logger.info(f'==ORDER=={order_.pos_reference}')
                _logger.info(f'==ORDER_DATE=={order_.date_order}')
                _logger.info(f'==ORDER_AMOUNT_PAID=={order_.amount_paid}')
                _logger.info(f'==ORDER_TAX_AMOUNT=={order_.amount_tax}')
                _logger.info(f'==ORDER_PAYMENT_METHOD=={order_.payment_ids.payment_method_id.name}')
                _logger.info(f'==CUSTOMER=={order_.partner_id.name}')
                _logger.info(f'==PRODUCT=={line.product_id.name}')
                _logger.info(f'==LINE_PRICE=={line.price_unit}')
                _logger.info(f'==LINE_QTY=={line.qty}')
                _logger.info(f'==LINE_TAX_IDS=={line.tax_ids}')
                _logger.info(f'==LINE_TAX_FISCAL=={line.tax_ids_after_fiscal_position}')
                _logger.info(f'==LINE_UOM=={line.product_uom_id.name}')
                _logger.info('')

            send = self._l10n_ke_oscu_save_item(order_)
            _logger.info('***************send*************** %s', send)

            json=self._l10n_ke_oscu_json_from_move(order_)
            _logger.info('***************json***************')
            _logger.info(json)

            send_pos_order = self._l10n_ke_oscu_send_customer_invoice(order_)
            _logger.info('***************send*************** %s', send_pos_order)
            return send_pos_order
        return order


    def _l10n_ke_oscu_json_from_move(self, order):
        """ Get the json content of the TrnsSalesSaveWr/TrnsPurchaseSave request from a move. """

        confirmation_datetime = format_etims_datetime(fields.Datetime.now())

        invoice_date = order.date_order or ''
        _logger.info(f'=============INVOICE_DATE========== {invoice_date}')

        original_invoice_number = order.sequence_number or 0
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

        _logger.info(f"====TYPECODE===={order.payment_ids.mapped('payment_method_id.l10n_ke_payment_method_id').code or ''}")

        content = {
            'invcNo': order.sequence_number,  # KRA Invoice Number (set at the point of sending)
            'trdInvcNo': (order.pos_reference or '')[:50],  # Trader system invoice number
            'orgInvcNo': original_invoice_number,  # Original invoice number
            'cfmDt': confirmation_datetime,  # Validated date
            'pmtTyCd': order.payment_ids.mapped('payment_method_id.l10n_ke_payment_method_id').code or '',  # Payment type code
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

        # is_purchase means account move move_type in ['in_invoice', 'in_refund', 'in_receipt']
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
            'salesDt': invoice_date.strftime('%Y%m%d'),  # Sales date
            'prchrAcptcYn': 'Y',
            'receipt': receipt_part,
        })

        if self.has_refundable_lines:
            content.update({'rfdRsnCd': self.l10n_ke_reason_code_id.code if self.l10n_ke_reason_code_id.code else ''})
        return content

    def _calculate_l10n_ke_item_code(self, product):
        """ Computes the item code of a given product

        For instance KE1NTXU is an item code, where
        KE:      first two digits are the origin country of the product
        1:       the product type (raw material)
        NT:      the packaging type
        XU:      the quantity type
        0000006: a unique value (id in our case)
        """
        code_fields = [
            product.l10n_ke_origin_country_id.code,
            product.l10n_ke_product_type_code,
            product.l10n_ke_packaging_unit_id.code,
            product.uom_id.l10n_ke_quantity_unit_id.code,
        ]
        if not all(code_fields):
            return None

        item_code_prefix = ''.join(code_fields)
        return item_code_prefix.ljust(20 - len(str(self.id)), '0') + str(self.id)


    def _l10n_ke_oscu_save_item_content(self, order):
        """ Get a dict of values to be sent to the KRA for saving a product's information. """
        content = {}

        for index, line in enumerate(order.lines):
            product = line.product_id  # for ease of reference

            code = product.l10n_ke_item_code or self._calculate_l10n_ke_item_code(product)
            content = {
                'itemCd':      code if code else "", # Item Code
                'itemClsCd':   product.unspsc_code_id.code if product.unspsc_code_id.code else "", # HS Code (unspsc format)
                'itemTyCd':    product.l10n_ke_product_type_code if product.l10n_ke_product_type_code else '2',  # Generally raw material, finished product, service
                'itemNm':      product.name,                                             # Product name
                'orgnNatCd':   product.l10n_ke_origin_country_id.code if product.l10n_ke_origin_country_id.code else "KE",  # Origin nation code
                'pkgUnitCd':   product.l10n_ke_packaging_unit_id.code if product.l10n_ke_packaging_unit_id.code else 'NT',  # Packaging unit code
                'qtyUnitCd':   product.uom_id.l10n_ke_quantity_unit_id.code,             # Quantity unit code
                'taxTyCd':     'B',                                                      # Tax type code
                'bcd':         product.barcode or None,                                  # Self barcode
                'dftPrc':      product.standard_price,                                   # Standard price
                'isrcAplcbYn': 'Y' if product.l10n_ke_is_insurance_applicable else 'N',  # Is insurance applicable
                'useYn': 'Y',
                **self.env.company._l10n_ke_get_user_dict(self.create_uid, self.write_uid),
            }
        return content

    def _l10n_ke_oscu_save_item(self, order):
        """ Register a product with eTIMS. """
        content = self._l10n_ke_oscu_save_item_content(order)
        _logger.info(self.env.company)
        _logger.info(content)
        error, _data, _date = self.env.company._l10n_ke_call_etims('items/saveItems', content)
        if not error:
            for index, line in enumerate(order.lines):
                product = line.product_id
                product.l10n_ke_item_code = content['itemCd']
        return error, content


    def _l10n_ke_oscu_get_json_from_lines(self, order):
        """ Return the values that should be sent to eTIMS for the lines in self. """
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
                'itemCd': product.l10n_ke_item_code if product.l10n_ke_item_code else "",  # Item code as defined by us, of the form
                'itemClsCd': product.unspsc_code_id.code if product.unspsc_code_id.code else "",  # Item classification code, in this case the UNSPSC code
                'itemNm': line.product_id.name,  # Item name
                'pkgUnitCd': product.l10n_ke_packaging_unit_id.code if product.l10n_ke_packaging_unit_id.code else 'NT',
                # Packaging code, describes the type of package used
                'pkg': product_uom_qty / product.l10n_ke_packaging_quantity,  # Number of packages used
                'qtyUnitCd': line.product_uom_id.l10n_ke_quantity_unit_id.code,
                # The UOMs as defined by the KRA, defined seperately from the UOMs on the line
                'qty': line.qty,
                'prc': price_unit,
                'splyAmt': price_subtotal_before_discount,
                'dcRt': line.discount,
                'dcAmt': discount_amount,
                'taxTyCd': 'B',
                'taxblAmt': line.price_subtotal,
                'taxAmt': line.price_subtotal_incl - line.price_subtotal,
                'totAmt': line.price_subtotal_incl,
                "isrccCd": '',
                "isrccNm": '',
                "isrcRt": '',
                "isrcAmt": '',
            }

            fields_to_round = ('pkg', 'qty', 'prc', 'splyAmt', 'dcRt', 'dcAmt', 'taxblAmt', 'taxAmt', 'totAmt')
            for field in fields_to_round:
                line_values[field] = self.json_float_round(line_values[field], 2)

            if product.barcode:
                line_values.update({'bcd': product.barcode})

            lines_values.append(line_values)
        return lines_values

    def format_code(self, code):
        return '-'.join([code[i:i + 4] for i in range(0, len(code), 4)])

    def extract_date_time(self, datetime_str):
        # Parse the string into a datetime object
        dt = datetime.strptime(datetime_str, '%Y%m%d%H%M%S')
        return dt

    def _l10n_ke_oscu_send_customer_invoice(self, order):
        content = self._l10n_ke_oscu_json_from_move(order)

        _logger.info('====PAYLOAD==== %s', content)

        error, data, _date = self.env.company._l10n_ke_call_etims('trnsSales/saveSales', content)
        if not error:
            if data:
                lines = order.lines
                number_of_items = len(lines)
                _logger.info(f'====Number of items:==== {number_of_items}')

                total_before_discount = 0
                discount_amount = 0
                for line in lines:
                    price_after_discount = line.price_unit
                    subtotal_after_discount = price_after_discount * line.qty
                    total_before_discount += subtotal_after_discount
                    discount = line.price_unit * (line.discount or 0.0) / 100.0
                    discount_amount += discount

                rcpt_no = data.get('rcptNo')
                intrl_data = self.format_code(data.get('intrlData'))
                rcpt_sign = self.format_code(data.get('rcptSign'))
                tot_rcpt_no = data.get('totRcptNo')
                vsdc_rcpt_pbct_date = self.extract_date_time(data.get('vsdcRcptPbctDate'))
                vsdc_rcpt_date = vsdc_rcpt_pbct_date.strftime('%d-%m-%Y')
                vsdc_rcpt_time = vsdc_rcpt_pbct_date.strftime('%H:%M:%S')
                sdc_id = data.get('sdcId')
                mrc_no = data.get('mrcNo')

                taxblAmtA = content.get('taxblAmtA', "")
                taxblAmtB = content.get('taxblAmtB', "")
                taxblAmtC = content.get('taxblAmtC', "")
                taxblAmtD = content.get('taxblAmtD', "")
                taxblAmtE = content.get('taxblAmtE', "")
                taxAmtA = content.get('taxAmtA', "")
                taxAmtB = content.get('taxAmtB', "")
                taxAmtC = content.get('taxAmtC', "")
                taxAmtD = content.get('taxAmtD', "")
                taxAmtE = content.get('taxAmtE', "")
                pmtTyCd = content.get('pmtTyCd', "")

                # Print values to verify
                _logger.info(f"===rcpt_no===: {rcpt_no}")
                _logger.info(f"===intrl_data===: {intrl_data}")
                _logger.info(f"===rcpt_sign===: {rcpt_sign}")
                _logger.info(f"===tot_rcpt_no===: {tot_rcpt_no}")
                _logger.info(f"===vsdc_rcpt_pbct_date===: {vsdc_rcpt_date}")
                _logger.info(f"===vsdc_rcpt_pbct_time===: {vsdc_rcpt_time}")
                _logger.info(f"===sdc_id===: {sdc_id}")
                _logger.info(f"===mrc_no===: {mrc_no}")

                kra_pin = self.env.company.kra_pin
                branch_id = self.env.company.l10n_ke_branch_code
                rcpt_sign = data.get('rcptSign')
                qr_url = f'https://etims.kra.go.ke/common/link/etims/receipt/indexEtimsReceptData?{kra_pin}+{branch_id}+{rcpt_sign}'

                data['l10n_ke_qr_code'] = qr_url
                data['intrlData'] = self.format_code(data.get('intrlData', ''))
                data['rcptSign'] = self.format_code(data.get('rcptSign', ''))
                data['rcpt_no'] = rcpt_no
                data['sdc_id'] = sdc_id
                data['cu_invoice_no'] = f'{sdc_id}/{rcpt_no}'
                data['vsdc_rcpt_time'] = vsdc_rcpt_time
                data['vsdc_rcpt_date'] = vsdc_rcpt_date
                data['number_of_items'] = number_of_items
                data['total_before_discount'] = total_before_discount
                data['discount_amount'] = discount_amount
                data['taxblAmtA'] = taxblAmtA
                data['taxblAmtB'] = taxblAmtB
                data['taxblAmtC'] = taxblAmtC
                data['taxblAmtD'] = taxblAmtD
                data['taxblAmtE'] = taxblAmtE
                data['taxAmtA'] = taxAmtA
                data['taxAmtB'] = taxAmtB
                data['taxAmtC'] = taxAmtC
                data['taxAmtD'] = taxAmtD
                data['taxAmtE'] = taxAmtE
                data['pmtTyCd'] = pmtTyCd

                self.write({
                    'l10n_ke_oscu_receipt_number': data['rcptNo'],
                    'l10n_ke_control_unit': data['sdcId'],
                    'l10n_ke_oscu_invoice_number': content['invcNo'],
                    'l10n_ke_oscu_signature': data['rcptSign'],
                    'l10n_ke_oscu_datetime': parse_etims_datetime(data['vsdcRcptPbctDate']),
                    'l10n_ke_oscu_internal_data': data['intrlData'],
                    'l10n_ke_qr_code': qr_url,
                })

        _logger.info('====ERROR==== %s', error)
        _logger.info('====RESPONSE==== %s', data)
        _logger.info('====DATE==== %s', _date)
        _logger.info('====DATA==== %s', content)

        return data

