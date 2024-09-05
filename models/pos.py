import logging
from datetime import datetime
import time
import json 
from odoo import fields, models, api
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_round, float_compare
import qrcode
import json
from io import BytesIO
from qrcode import QRCode, constants
import base64
from .etims_connect import ETIMSConnect

from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)
import requests


class PosSession(models.Model):
    _inherit = "pos.session"

  
    
class PosOrder(models.Model):
    _name = 'pos.order'
    _inherit = ['pos.order', 'portal.mixin',]
    


    ke_etims_result_dt = fields.Char(string='Result DateTime', size=14, no_copy=True)
    ke_etims_cur_rcpt_no = fields.Char(string='Current Receipt Number', size=50, no_copy=True)
    ke_etims_tot_rcpt_no = fields.Integer(string='Total Receipt Number', no_copy=True)
    ke_etims_intrl_data = fields.Char(string='Internal Data', size=100, no_copy=True)
    ke_etims_intrl_data_formatted = fields.Char(string='Internal Data Formatted',compute="format_ke_etims_intrl_data", no_copy=True,
                                                )
    ke_etims_rcpt_sign = fields.Char(string='Receipt Signature', )
    ke_etims_credit_note_sign = fields.Char(string='Credit Note Signature', no_copy=True)

    ke_etims_rcpt_sign_formatted = fields.Char(string='Receipt Signature Formatted',compute="_compute_ke_etims_rcpt_sign_formatted"  )
    ke_etims_sdc_date_time = fields.Datetime(string='SDC Date Time')
    sdcId = fields.Char(string='SDC ID', size=50, no_copy=True)
    mrcNo = fields.Char(string='MRC Number', no_copy=True)
    ke_etims_qr_code_url = fields.Char(string='QR Code URL', no_copy=True)

    branch_seq = fields.Char(string='Branch Receipt No/sequence', no_copy=True,)

    tax_mapping = fields.Json(string='Tax Mapping', compute='_compute_tax_fields_v2')


    def format_ke_etims_intrl_data(self):
        # Ensure that self.ke_etims_intrl_data is a string
        if not isinstance(self.ke_etims_intrl_data, str):
            self.ke_etims_intrl_data_formatted = ''
            return

        # put dash after every 4 characters
        self.ke_etims_intrl_data_formatted = '-'.join(
            [self.ke_etims_intrl_data[i:i + 4] for i in range(0, len(self.ke_etims_intrl_data), 4)])

        self.ke_etims_rcpt_sign_formatted = '-'.join(
            [self.ke_etims_rcpt_sign[i:i + 4] for i in range(0, len(self.ke_etims_rcpt_sign), 4)])

    def _compute_ke_etims_rcpt_sign_formatted(self):
        # put dash after every 4 characters
        self.ke_etims_rcpt_sign_formatted = '-'.join(
            [self.ke_etims_rcpt_sign[i:i + 4] for i in range(0, len(self.ke_etims_rcpt_sign), 4)])

    etims_qr_code = fields.Binary(
        string='Etims QR Code', copy=False, readonly=True)

    def _make_signature_qrcode(self, url):
        qr = QRCode(version=1, box_size=25, border=6, error_correction=constants.ERROR_CORRECT_L)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')
        temp_img = BytesIO()
        img.save(temp_img, format='PNG')
        return base64.b64encode(temp_img.getvalue())

    def compute_qr_code_str(self):
        str_to_encode = self.ke_etims_qr_code_url
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(str_to_encode)
        qr.make(fit=True)
        img = qr.make_image()
        temp = BytesIO()
        img.save(temp, format="PNG")
        qr_image = base64.b64encode(temp.getvalue())
        return qr_image

    def _prepare_item_list(self, invoice_lines):
            item_list = []
            for idx, line in enumerate(invoice_lines):
                discount_amount = 0
                if line.discount > 0:
                    discount_amount = (line.discount / 100) * line.price_unit
                item = {
                    "itemSeq": idx + 1,
                    "itemCd": line.product_id.l10n_ke_item_code,  # Item Classification Code
                    "itemClsCd": line.product_id.unspsc_code_id.code if line.product_id.unspsc_code_id else "null",
                    # Item Code
                    "itemNm": line.name or '',  # tem Name
                    "bcd": "null",  # barcode not required
                    "pkgUnitCd": line.product_id.l10n_ke_packaging_unit_id.code,  # packing unit code
                    "pkg": line.qty,  # Package
                    "qtyUnitCd": line.product_uom_id.l10n_ke_quantity_unit_id.code,  # Quantity Unit Code
                    "qty": line.qty,
                    "prc": line.price_unit,  # Unit Price inclusivve of tax
                    "splyAmt": line.price_subtotal_incl,  # Supply Amount
                    "dcRt": line.discount,  # Discount Rate
                    "dcAmt": discount_amount,  # Discount Amount
                    "isrccCd": "null",  # Insurance Company Code
                    "isrccNm": "null",  # Insurance Company Name
                    "isrcRt": "null",  # Insurance Rate
                    "isrcAmt": "null",  # Insurance Amount
                    "taxTyCd": line.tax_ids.l10n_ke_tax_type_id,  # Taxation Type Code
                    "taxblAmt": line.price_subtotal,  # Taxable Amount, Tax included amount
                    "taxAmt": round(line.price_subtotal_incl - line.price_subtotal, 2),  # Tax Amount
                    "totAmt": line.price_subtotal_incl  # Total Amount
                }
                item_list.append(item)
                # _logger.info('=========<<<<<<<<<<<<<<<<<<<<<<<<<Items in list<<<<<<<<<<<<<<<<<<<<<<<<<<<<===========')
                _logger.info(item_list)

            return item_list
    
    def _prepare_tax_lines(self, invoice_lines):
            """
            Prepare the item list for the payload from given invoice lines.
            """
            tax_list = []
            for idx, line in enumerate(invoice_lines):
                # _logger.info('=========line===========')
                # _logger.info(line.tax_ids)
                for tax in line.tax_ids:
                    item = {
                        "itemSeq": idx + 1,
                        "taxTyCd": tax.tax_code,  # Taxation Type Code
                        "taxblAmt": line.price_subtotal,  # Taxable Amount, Tax included amount
                        "taxAmt": round(line.price_subtotal_incl - line.price_subtotal, 2),  # Tax Amount
                        "totAmt": line.price_subtotal_incl  # Total Amount
                    }
                    tax_list.append(item)
            return tax_list
    
    def get_tax_rate_by_class(self, tax_class):
        """
        Get the tax rate for the given tax class.
        """
        # search etims.code.lines where code_class_name ='Taxation Type' and cd = tax_class
        # # return the tax rate
        # tax_code = self.env['etims.code.lines'].search([('cd_cls_nm', '=', 'Taxation Type'), ('cd', '=', tax_class)])
        # return tax_code.user_dfn_cd1

        return 16
    

    def _l10n_ke_get_invoice_sequence(self):
        """ Returns the KRA invoice sequence for this invoice (company and move_type dependent), creating it if needed. """
        self.ensure_one()

        sequence_code = 'l10n.ke.oscu.sale.sequence' if self.is_sale_document(include_receipts=True) else 'l10n.ke.oscu.purchase.sequence'

        if not (sequence := self.env['ir.sequence'].search([
            ('code', '=', sequence_code),
            ('company_id', '=', self.company_id.id),
        ])):
            sequence_name = 'eTIMS Customer Invoice Number' if self.is_sale_document(include_receipts=True) else 'eTIMS Vendor Bill Number'
            return self.env['ir.sequence'].create({
                'name': sequence_name,
                'implementation': 'no_gap',
                'company_id': self.company_id.id,
                'code': sequence_code,
            })
        return sequence
        

    def send_to_etims(self):
        api = ETIMSConnect(self.env.company.kra_pin, self.env.company.l10n_ke_branch_code)
        _logger.info(f'==========ETIMS_CONNECT========= {api}')
        item_list = self._prepare_item_list(self.lines)
        tax_ids = self._prepare_tax_lines(self.lines.filtered(lambda l: l.qty and l.price_subtotal_incl > 0))
        payload = {
            "tin": self.company_id.kra_pin,
            "bhfId": self.env.company.l10n_ke_branch_code,
            "trdInvcNo": self.name,
            "invcNo": "null",
            "orgInvcNo": '0',  # Id of the invoice generating Credit note
            "custTin": self.partner_id.vat,
            "custNm": self.partner_id.name,
            "salesTyCd": "N",
            "rcptTyCd": 'S',
            "pmtTyCd": '01',
            "salesSttsCd": "02",
            "cfmDt": self.date_order.strftime('%Y%m%d%H%M%S'),
            "salesDt": self.date_order.strftime('%Y%m%d'),
            "stockRlsDt": self.date_order.strftime('%Y%m%d%H%M%S'),
            "totItemCnt": len(self.lines),
            "taxblAmtA": sum(tax['taxblAmt'] for tax in tax_ids if tax['taxTyCd'] == 'A'),
            "taxblAmtB": sum(tax['taxblAmt'] for tax in tax_ids if tax['taxTyCd'] == 'B'),
            "taxblAmtC": sum(tax['taxblAmt'] for tax in tax_ids if tax['taxTyCd'] == 'C'),
            "taxblAmtD": sum(tax['taxblAmt'] for tax in tax_ids if tax['taxTyCd'] == 'D'),
            "taxblAmtE": sum(tax['taxblAmt'] for tax in tax_ids if tax['taxTyCd'] == 'E'),
            "taxRtA": self.get_tax_rate_by_class('A'),
            "taxRtB": self.get_tax_rate_by_class('B'),
            "taxRtC": self.get_tax_rate_by_class('C'),
            "taxRtD": self.get_tax_rate_by_class('D'),
            "taxRtE": self.get_tax_rate_by_class('E'),
            "taxAmtA": 0,
            "taxAmtB": 0,
            "taxAmtC": 0,
            "taxAmtD": 0,
            "taxAmtE": 0,
            "totTaxblAmt": round(sum(self.lines.mapped('price_subtotal')), 2),
            "totTaxAmt": round(
                sum(self.lines.mapped('price_subtotal_incl')) - sum(self.lines.mapped('price_subtotal')),
                2),
            "totAmt": sum(self.lines.mapped('price_subtotal_incl')),
            "prchrAcptcYn": "N",
            "remark": "null",
            'regrId': self._uid,
            'regrNm': self.env.user.name,
            'modrId': self._uid,
            'modrNm': self.env.user.name,
            "receipt": {
                "custTin": self.partner_id.vat or '',
                "custMblNo": self.partner_id.phone or '',
                "rcptPbctDt": str(datetime.now().strftime('%Y%m%d%H%M%S')),
                "trdeNm": "null",
                "adrs": "null",
                "topMsg": "null",
                "btmMsg": "null",
                "prchrAcptcYn": "N"
            },
            "itemList": item_list
        }
        self.branch_seq = payload.get('invcNo')
        # return

        try:
            _logger.info('=========payload===========')
            _logger.info(payload)
            _logger.info('=========payload===========')
            # response = requests.post(api_endpoint, json=payload, headers=headers)
            response_data = api.save_move(json.dumps(payload))

            _logger.info('========response_data========')
            _logger.info(response_data)
            _logger.info('========response_data========')

            if response_data.get('resultCd') != '000':
                _logger.error(response_data.get('resultMsg'))
                raise UserError(f"API Error: {response_data.get('resultMsg')}")

            # Process the response
            _logger.info('=========response===========')
            _logger.info(json.dumps(response_data))

            data = response_data.get('data')
        

            self.ke_etims_result_dt = data.get('resultDt')
            self.ke_etims_cur_rcpt_no = data.get('rcptNo')
            self.ke_etims_tot_rcpt_no = data.get('totRcptNo')
            self.ke_etims_intrl_data = data.get('intrlData')
            self.ke_etims_rcpt_sign = data.get('rcptSign')
            # self.tt = _make_signature_qrcode(data.)
            self.ke_etims_sdc_date_time = datetime.strptime(data.get('vsdcRcptPbctDate'), "%Y%m%d%H%M%S")
            self.sdcId = data.get('sdcId')
            # self.mrcNo = data.get('mrcNo')
            base_url = 'https://etims-sbx.kra.go.ke/common/link/etims/receipt/indexEtimsReceiptData?' if self.company_id.etims_test_mode else 'https://etims.kra.go.ke/common/link/etims/receipt/indexEtimsReceptData?'

            self.ke_etims_qr_code_url = base_url + 'Data=' + self.company_id.kra_pin + self.company_id.branch_id + str(data.get('rcptSign'))

            self.etims_qr_code= self._make_signature_qrcode(self.ke_etims_qr_code_url)

        except requests.RequestException as e:
            raise UserError(f"Network or API communication error: {str(e)}")
        

# < calling StockIO and stock master
        

    def set_sequence(self):
        bhf_id = self.env.user.branch_id.bhf_id
        code = 'etims.stock.sequence.branch.' + bhf_id
        _logger.info('=====code=====')
        # _logger.info(code)
        seq = self.env['ir.sequence'].sudo().next_by_code(code)
        return seq
        
        
    def init_stock_move(self):
        api = ETIMSConnect(self.env.company.kra_pin, self.env.user.branch_id.bhf_id)
        payload = self._create_stock_moves_payload()
        _logger.info('==========================init_stock_move-request==========================')
        response_data = api.move_stock(json.dumps(payload))
        if response_data.get('resultCd') != '000':
            _logger.error(response_data.get('resultMsg'))
            raise UserError(f"API Error: {response_data.get('resultMsg')}")
        # self.branch_seq = payload.get('sarNo')
        return True

    def _create_stock_moves_payload(self):
        # # if not self.location_dest_id.branch_id:
        # #     raise UserError(f'The location {self.location_dest_id.name} is not linked to a branch')
        # etims_origin_sar_number = 0
        # if self.etims_stock_move == '03':
        #     etims_origin_sar_number = self.origin_sar_number
        items = self.get_item_list(self.lines)
        payload = {
            'tin': self.env.company.kra_pin,
            'bhfId': self.env.company.l10n_ke_branch_code,
            'sarNo': self.set_sequence(),  # should be unique and autoincrement
            'orgSarNo': '0',  # todo set as spplrInvcNo from the purchase order created
            'regTyCd': 'M',
            'sarTyCd': "11",  # for incoming purchases should be 02
            'ocrnDt': datetime.now().strftime('%Y%m%d'),  # date when product occured
            'custTin': self.partner_id.vat,  # for inter branch this should be the new branch, for sales is the customer
            'custNm': self.partner_id.name,

            'custBhfId': self.partner_id.etims_branch_id.l10n_ke_branch_code if self.partner_id.etims_branch_id.l10n_ke_branch_code else '00',
            'totItemCnt': len(self.lines),  # number in list
            'totTaxblAmt': sum(data['taxblAmt'] for data in items),
            'totTaxAmt': round(sum(data['taxAmt'] for data in items), 2),
            'totAmt': sum(data['totAmt'] for data in items),
            'remark': 'Stock Movement',
            'regrId': self.env.user.name,
            'regrNm': self.env.user.name,
            'modrId': self.env.user.name,
            'modrNm': self.env.user.name,
            'itemList': items
        }
        return payload

    def get_item_list(self, lines):
        items = []
        for idx, line in enumerate(lines):
            product = line.product_id
            if (not product.l10n_ke_item_code or not product.item_class_code or not product.l10n_ke_packaging_unit_id
                    or not product.l10n_ke_quantity_unit_id or not product.list_price
                    or not product.etims_origin_country
                    or not product.etims_product_type or not product.l10n_ke_quantity_unit_id or not product.l10n_ke_packaging_unit_id):
                raise UserError(
                    f'Product {product.name} is not fully configured for eTIMS. Please check the product configuration.')
            tax_amount = line.product_id.taxes_id.amount / 100
            item = {
                "itemSeq": idx + 1,
                "itemCd": line.product_id.l10n_ke_item_code,  # Item Classification Code
                "itemClsCd": line.product_id.item_class_code.item_cls_cd if line.product_id.item_class_code else "null",
                # Item Code
                "itemNm": line.name or '',  # tem Name
                "bcd": "null",  # barcode not required
                "pkgUnitCd": line.product_id.l10n_ke_packaging_unit_id.code,  # packing unit code
                "pkg": line.qty,  # Package
                "qtyUnitCd": line.product_id.etims_quantity_unit_code.cd,  # Quantity Unit Code
                "qty": line.qty,
                "prc": line.product_id.list_price,  # Unit Price
                "splyAmt": line.product_id.standard_price * line.qty,  # Supply Amount
                'totDcAmt': 0,
                'taxblAmt': line.product_id.list_price * line.qty,
                'taxTyCd': line.product_id.taxes_id.tax_code,
                'taxAmt': tax_amount * (line.product_id.list_price * line.qty),
                'totAmt': line.product_id.list_price * line.qty,  # multiplied by qty
            }
            items.append(item)
        return items

    def action_pos_order_paid(self):
        res = super().action_pos_order_paid()
        self.send_to_etims()
        self.init_stock_move()
        return res

    def _compute_tax_fields_v2(self):
        # get all taxes for pos receipt
        all_taxes = []
        taxes = self.env['account.tax'].search(
            [('tax_code', '!=', False), ('type_tax_use', '=', 'sale'),
             ('company_id', '=', self.company_id.id)
             ])
        for tax in taxes:
            # check i added to all_taxes

            # get all taxes of this type
            tax_lines = self.lines.filtered(lambda l: tax in l.tax_ids)
            taxbl_amt = sum(tax_lines.mapped('price_subtotal'))
            tax_amt = sum(tax_lines.mapped('price_subtotal_incl')) - taxbl_amt
            item_count = len(tax_lines)
            # get selection value for tax code
            value = dict(self.env['account.tax']._fields['tax_code'].selection).get(tax.tax_code)

            all_taxes.append({
                'tax_code': value,
                'name': tax.name,
                'taxbl_amt': round(taxbl_amt, 2),
                'tax_amt': round(tax_amt, 2),
                'item_count': item_count
            })

        _logger.info('=========all_taxes===========')
        _logger.info(json.dumps(all_taxes))
        self.tax_mapping = all_taxes

        pass

    @api.model
    def tims_receipt_payload(self, ref):
        order = self.env['pos.order'].search([('pos_reference', '=', ref)], limit=1)
        payload ={
            'ke_etims_rcpt_sign' :order.ke_etims_rcpt_sign,
            'ke_etims_sdc_date_time' : order.ke_etims_sdc_date_time,
            'sdcId' : order.sdcId,
            'etims_qr_code' : order.etims_qr_code,
            'branch_seq' : order.branch_seq,
            'ke_etims_intrl_data_formatted' : order.ke_etims_intrl_data_formatted,
            'ke_etims_rcpt_sign_formatted' : order.ke_etims_rcpt_sign_formatted,
            'tax_mapping' : order.tax_mapping,
        
            
        }
        _logger.info('<<<<<<<<<<<<<<<<<<<<<<<tims_receipt_payload order={} and {}'.format(order,payload))
        return payload
    

   