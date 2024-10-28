odoo.define('l10n_ke_etims_vscu_pos.PaymentScreen', function (require) {
    'use strict';

    const Registries = require("point_of_sale.Registries");
    const PaymentScreen = require("point_of_sale.PaymentScreen");
    const rpc = require("web.rpc");
    const { Gui } = require('point_of_sale.Gui');

    const PaymentScreenExtend = PaymentScreen => class extends PaymentScreen {

         async _finalizeValidation() {
            const order = this.currentOrder;
            const orderData = order.export_as_JSON(); // Collect order data to send to the backend
             let shouldFinalize = true;

             console.log('===================================', orderData)

             // # create the order in the backend
             // await  super._finalizeValidation();

            // Call your custom backend function via rpc before finalizing the order
            await rpc.query({
                model: 'pos.order',
                method: 'sign_order',
                args: [{}, orderData]
            }).then((result) => {
                console.log("===Custom function called successfully:===", result);
                if (result) {
                    order.pmtTyCd = result.pmtTyCd;
                    if (!order.pmtTyCd) {
                        Gui.showPopup('ErrorPopup', {
                            title: 'KRA E-TIMS ERROR',
                            body: 'Payment Type Code is empty..'
                        });
                        shouldFinalize = false;
                    }
                    order.ke_etims_rcpt_sign = result.rcptSign;
                    order.ke_etims_sdc_date_time = result.ke_etims_sdc_date_time;
                    order.l10n_ke_qr_code = result.l10n_ke_qr_code
                    order.branch_seq = result.branch_seq;
                    order.ke_etims_intrl_data_formatted = result.intrlData;
                    order.ke_etims_rcpt_sign_formatted = result.ke_etims_rcpt_sign_formatted;
                    order.tax_mapping = result.tax_mapping;
                    order.sdc_id = result.sdc_id;
                    order.rcpt_no = result.rcpt_no;
                    order.cu_invoice_no = result.cu_invoice_no
                    order.vsdc_rcpt_date = result.vsdc_rcpt_date
                    order.vsdc_rcpt_time = result.vsdc_rcpt_time
                    order.number_of_items = result.number_of_items
                    order.total_before_discount = result.total_before_discount
                    order.discount_amount = result.discount_amount
                    order.taxblAmtA = result.taxblAmtA
                    order.taxblAmtB = result.taxblAmtB
                    order.taxblAmtC = result.taxblAmtC
                    order.taxblAmtD = result.taxblAmtD
                    order.taxblAmtE = result.taxblAmtE
                    order.taxAmtA = result.taxAmtA
                    order.taxAmtB = result.taxAmtB
                    order.taxAmtC = result.taxAmtC
                    order.taxAmtD = result.taxAmtD
                    order.taxAmtE = result.taxAmtE
                }
                else{
                    // #pop up error message
                      Gui.showPopup('ErrorPopup', {
                    title: 'KRA E-TIMS ERROR',
                    body: 'There was an issue communicating with the server.',
                });
                      shouldFinalize = false;

                }
            }).catch((error) => {
                console.error("===Error calling custom function:===", error);
                // #pop up error message
                Gui.showPopup('ErrorPopup', {
                    title: 'KRA E-TIMS ERROR',
                    body: error
                });
                shouldFinalize = false;

            });

            // Call the original _finalizeValidation to complete the validation process
             if (shouldFinalize){
                 await  super._finalizeValidation();
                 return super._finalizeValidation();
             }

    }

        }

    Registries.Component.extend(PaymentScreen, PaymentScreenExtend);
});
