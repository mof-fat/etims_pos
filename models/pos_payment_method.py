import logging
from odoo import fields, models, api
_logger = logging.getLogger(__name__)

class PosPaymentMethos(models.Model):
    _inherit = 'pos.payment.method'
    l10n_ke_payment_method_id = fields.Many2one(
        string="eTIMS Payment Method",
        comodel_name='l10n_ke_etims_vscu.code',
        domain=[('code_type', '=', '07')],
        help="Method of payment communicated to the KRA via eTIMS. This is required when confirming purchases.",
    )