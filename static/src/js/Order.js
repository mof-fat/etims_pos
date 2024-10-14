odoo.define('l10n_ke_etims_vscu_pos.OrderReceipt', function (require) {
    "use strict";

    const Registries = require("point_of_sale.Registries");
    const OrderReceipt = require('point_of_sale.OrderReceipt')

    const OrderReceiptEsd = OrderReceipt =>
        class extends OrderReceipt {
            get receipt() {
                let res = super.receipt;
                let order = this.env.pos.get_order()

                // console.log('THIS ORDER>>>>>>>>>>>>>>>>>>order :', order);

                res.ke_etims_rcpt_sign = order.ke_etims_rcpt_sign;
                res.ke_etims_sdc_date_time = order.ke_etims_sdc_date_time;
                // order.esd_signature = result.esd_signature;
                res.l10n_ke_qr_code = order.l10n_ke_qr_code;
                res.branch_seq = order.branch_seq;
                res.ke_etims_intrl_data_formatted = order.ke_etims_intrl_data_formatted;
                res.ke_etims_rcpt_sign_formatted = order.ke_etims_rcpt_sign_formatted;
                res.tax_mapping = order.tax_mapping;
                res.sdc_id = order.sdc_id;
                res.rcpt_no = order.rcpt_no
                res.cu_invoice_no = order.cu_invoice_no
                res.vsdc_rcpt_date = order.vsdc_rcpt_date
                res.vsdc_rcpt_time = order.vsdc_rcpt_time
                res.number_of_items = order.number_of_items
                res.total_before_discount = order.total_before_discount
                res.discount_amount = order.discount_amount
                res.taxblAmtA = order.taxblAmtA
                res.taxblAmtB = order.taxblAmtB
                res.taxblAmtC = order.taxblAmtC
                res.taxblAmtD = order.taxblAmtD
                res.taxblAmtE = order.taxblAmtE
                res.taxAmtA = order.taxAmtA
                res.taxAmtB = order.taxAmtB
                res.taxAmtC = order.taxAmtC
                res.taxAmtD = order.taxAmtD
                res.taxAmtE = order.taxAmtE
                // console.log('MY RES<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<res :', res);

                return res
            }
        }
    Registries.Component.extend(OrderReceipt, OrderReceiptEsd)
})

