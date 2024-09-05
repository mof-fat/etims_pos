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
             // # create the order in the backend
             await  super._finalizeValidation(); //TODO check if this should be calledbefore our logic to ensure order is created
            // Call your custom backend function via rpc before finalizing the order
            await rpc.query({
                model: 'pos.order',
                method: 'sign_order',
                args: [{}, orderData]  // Pass order data to the custom backend function
            }).then((result) => {
                console.log("Custom function called successfully:", result);
                if (result) {
                    order.ke_etims_rcpt_sign = result.ke_etims_rcpt_sign;
                }
                else{
                    // #pop up error message
                      Gui.showPopup('ErrorPopup', {
                    title: 'KRA ETIMS ERROR',
                    body: 'There was an issue communicating with the server.',
                });

                }
            }).catch((error) => {
                console.error("Error calling custom function:", error);
                // #pop up error message
                Gui.showPopup('ErrorPopup', {
                    title: 'KRA ETIMS ERROR',
                    body: 'There was an issue communicating with the server.'
                });

            });

            // Call the original _finalizeValidation to complete the validation process
            return super._finalizeValidation();
    }

        }


    Registries.Component.extend(PaymentScreen, PaymentScreenExtend);
});
