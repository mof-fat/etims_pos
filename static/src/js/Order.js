odoo.define('l10n_ke_etims_vscu_pos.OrderReceipt', function (require) {
    "use strict";

    const Registries = require("point_of_sale.Registries");
    const OrderReceipt = require('point_of_sale.OrderReceipt')

    const OrderReceiptEsd = OrderReceipt =>
        class extends OrderReceipt {
            get receipt() {
                let res = super.receipt;
                let order = this.env.pos.get_order()
                console.log('THIS ORDER>>>>>>>>>>>>>>>>>>order :', order);

                res.ke_etims_rcpt_sign = order.ke_etims_rcpt_sign;
                res.ke_etims_sdc_date_time = order.ke_etims_sdc_date_time;
                // order.esd_signature = result.esd_signature;
                res.etims_qr_code = order.etims_qr_code;
                res.sdcId = order.sdcId;
                res.branch_seq = order.branch_seq;
                res.ke_etims_intrl_data_formatted = order.ke_etims_intrl_data_formatted;
                res.ke_etims_rcpt_sign_formatted = order.ke_etims_rcpt_sign_formatted;
                res.tax_mapping = order.tax_mapping;

                

                
                

                
                // res.sdcId = order.sdcId;



                console.log('MY RES<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<res :', res);

                return res
            }
        }
    Registries.Component.extend(OrderReceipt, OrderReceiptEsd)
})

