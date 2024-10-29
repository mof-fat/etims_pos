odoo.define('l10n_ke_etims_vscu_pos.OrderReceipt', function (require) {
    "use strict";

    const Registries = require("point_of_sale.Registries");
    const OrderReceipt = require('point_of_sale.OrderReceipt')
    const rpc = require("web.rpc");

    const OrderReceiptEsd = OrderReceipt =>
        class extends OrderReceipt {
            get receipt() {
                let res = super.receipt;
<<<<<<< HEAD
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
=======

                const order = rpc.query({
                    model: 'pos.order',
                    method: 'get_order',
                    args: [{}, res.name]
                }).then((result) => {

                    console.log('THIS ORDER>>>>>>>>>>>>>>>>>>order :', result);
                    // order.esd_signature = order.esd_signature;
                    res.etims_qr_code = result.etims_qr_code;
                    res.sdcId = result.sdcId;
                    res.branch_seq = result.branch_seq;
                    res.ke_etims_intrl_data_formatted = result.ke_etims_intrl_data_formatted;
                    res.ke_etims_rcpt_sign_formatted = result.ke_etims_rcpt_sign_formatted;
                    res.tax_mapping = result.tax_mapping;
                    res.sdc_id = result.sdc_id;
                    res.rcpt_no = result.rcpt_no;
                    res.cu_invoice_no = result.cu_invoice_no
                    res.vsdc_rcpt_date = result.vsdc_rcpt_date
                    res.vsdc_rcpt_time = result.vsdc_rcpt_time
                    res.number_of_items = result.number_of_items
                    res.total_before_discount = result.total_before_discount
                    res.discount_amount = result.discount_amount
                    res.taxblAmtA = result.taxblAmtA
                    res.taxblAmtB = result.taxblAmtB
                    res.taxblAmtC = result.taxblAmtC
                    res.taxblAmtD = result.taxblAmtD
                    res.taxblAmtE = result.taxblAmtE
                    res.taxAmtA = result.taxAmtA
                    res.taxAmtB = result.taxAmtB
                    res.taxAmtC = result.taxAmtC
                    res.taxAmtD = result.taxAmtD
                    res.taxAmtE = result.taxAmtE

                    console.log('MY RES<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<res :', res);
                }).catch((error) => {
                    console.error('Error retrieving order:', error);
                });
>>>>>>> 333b33197095c40a8c2b656a4bf8a7d89b6dce95

                return res
            }
        }
    Registries.Component.extend(OrderReceipt, OrderReceiptEsd)
})

