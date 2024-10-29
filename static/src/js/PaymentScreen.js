odoo.define('l10n_ke_etims_vscu_pos.PaymentScreen', function (require) {
    'use strict';

    const Registries = require("point_of_sale.Registries");
    const PaymentScreen = require("point_of_sale.PaymentScreen");
    const rpc = require("web.rpc");
    const { Gui } = require('point_of_sale.Gui');

    const PaymentScreenExtend = PaymentScreen => class extends PaymentScreen {

        async _finalizeValidation() {
        const order = this.env.pos.get_order();
        const orderData = order.export_as_JSON(); // Collect order data to send to the backend
        let shouldFinalize = true;

        try {
            // Call the custom backend function to get the payment code
            const paymentResult = await rpc.query({
                model: 'pos.order',
                method: 'get_payment_code',
                args: [{}, orderData]
            });

            console.log("===Custom function called successfully:===", paymentResult.pmtTyCd);

            if (paymentResult) {
                order.pmtTyCd = paymentResult.pmtTyCd;

                if (!order.pmtTyCd) {
                    Gui.showPopup('ErrorPopup', {
                        title: 'KRA E-TIMS ERROR',
                        body: 'Payment Type Code is empty..'
                    });
                    shouldFinalize = false;
                }
            }

            // Proceed to sign the order only if payment code is valid
            if (shouldFinalize) {
                await  super._finalizeValidation();

                const signResult = await rpc.query({
                    model: 'pos.order',
                    method: 'sign_order',
                    args: [{}, orderData]
                });

                console.log("===Custom function called successfully:===", signResult.pmtTyCd);

                if (signResult) {
                    order.pmtTyCd = signResult.pmtTyCd; // This might be redundant if it's already set

                    // Assign values from signResult to order
                    Object.assign(order, {
                        ke_etims_rcpt_sign: signResult.rcptSign,
                        ke_etims_sdc_date_time: signResult.ke_etims_sdc_date_time,
                        l10n_ke_qr_code: signResult.l10n_ke_qr_code,
                        branch_seq: signResult.branch_seq,
                        ke_etims_intrl_data_formatted: signResult.intrlData,
                        ke_etims_rcpt_sign_formatted: signResult.ke_etims_rcpt_sign_formatted,
                        tax_mapping: signResult.tax_mapping,
                        sdc_id: signResult.sdc_id,
                        rcpt_no: signResult.rcpt_no,
                        cu_invoice_no: signResult.cu_invoice_no,
                        vsdc_rcpt_date: signResult.vsdc_rcpt_date,
                        vsdc_rcpt_time: signResult.vsdc_rcpt_time,
                        number_of_items: signResult.number_of_items,
                        total_before_discount: signResult.total_before_discount,
                        discount_amount: signResult.discount_amount,
                        taxblAmtA: signResult.taxblAmtA,
                        taxblAmtB: signResult.taxblAmtB,
                        taxblAmtC: signResult.taxblAmtC,
                        taxblAmtD: signResult.taxblAmtD,
                        taxblAmtE: signResult.taxblAmtE,
                        taxAmtA: signResult.taxAmtA,
                        taxAmtB: signResult.taxAmtB,
                        taxAmtC: signResult.taxAmtC,
                        taxAmtD: signResult.taxAmtD,
                        taxAmtE: signResult.taxAmtE,
                    });
                } else {
                    Gui.showPopup('ErrorPopup', {
                        title: 'KRA E-TIMS ERROR',
                        body: 'There was an issue communicating with the server.',
                    });
                    shouldFinalize = false;
                }
            }

            // Call the original _finalizeValidation to complete the validation process
            if (shouldFinalize) {
                await super._finalizeValidation();
            }

        } catch (error) {
            console.error("===Error calling custom function:===", error);
            Gui.showPopup('ErrorPopup', {
                title: 'KRA E-TIMS ERROR',
                body: error.toString()
            });
        }
        }
        }

    Registries.Component.extend(PaymentScreen, PaymentScreenExtend);
});
