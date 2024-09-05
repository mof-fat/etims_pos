odoo.define('etims_pos.PaymentScreen', function (require) {
    'use strict';

    const Registries = require("point_of_sale.Registries");
    const PaymentScreen = require("point_of_sale.PaymentScreen");
    const rpc = require("web.rpc");

    const PaymentScreenExtend = PaymentScreen => class extends PaymentScreen {

        async _finalizeValidation() {
            await super._finalizeValidation(...arguments);
            await this.tims_sign_receipt();
        }

        async tims_sign_receipt() {
            const self = this
            console.log('self.env.pos.company .........................:', self.env.pos.company);
            // if (self.env.pos.company.etims_device_serial_number) {
            const order = self.env.pos.get_order();

            await rpc.query({
                model: "pos.order",
                method: "tims_receipt_payload",
                args: [order.name],
            }).then(function (result) {
                console.log('result><>>>>>>>>>>>>>>>>>>>>>> :', result);
                order.ke_etims_rcpt_sign = result.ke_etims_rcpt_sign;
                order.ke_etims_sdc_date_time = result.ke_etims_sdc_date_time;
                order.sdcId = result.sdcId;
                order.etims_qr_code = result.etims_qr_code;
                order.branch_seq = result.branch_seq;
                order.ke_etims_rcpt_sign_formatted = result.ke_etims_rcpt_sign_formatted;
                order.ke_etims_intrl_data_formatted = result.ke_etims_intrl_data_formatted;
                order.tax_mapping = result.tax_mapping;
                


                
                

                
            });
            // }
        }
    }


    Registries.Component.extend(PaymentScreen, PaymentScreenExtend);
});
