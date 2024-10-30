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

            console.log("===Custom function called successfully:===", paymentResult);

            if (paymentResult) {

                const product_info = paymentResult.product_info;
                console.log("===product info:===", product_info);

                const fields = {
                    pmtTyCd: 'Payment Type Code is empty',
                    itemCd: 'Item Code is empty',
                    itemTyCd: 'Item Type Code is empty',
                    orgnNatCd: 'Origin Place Code is empty',
                    qtyUnitCd: 'Quantity unit Code is empty',
                    pkgUnitCd: 'Packaging Unit Code is empty',
                    taxTyCd: 'Taxation Type Code is empty',
                    regrId: 'Registrant ID is empty',
                    regrNm: 'Registrant Name is empty',
                    modrId: 'Modifier ID is empty',
                    modrNm: 'Moderator Name is empty',
                };

                let errorMessages = [];


                // Process each product in product_info
                product_info.forEach(product => {
                    Object.keys(fields).forEach(field => {
                        // Skip ignored fields
                        if (['regrId', 'regrNm', 'modrId', 'modrNm','pmtTyCd'].includes(field)) {
                            return; // Skip to the next iteration
                        }

                        // Check if the field exists in the product
                        if (product.hasOwnProperty(field)) {
                            order[field] = product[field];
                            if (!order[field]) {
                                errorMessages.push(`${fields[field]} for: ${product.product_name}.`);
                            }
                        }
                    });
                });

                Object.keys(fields).forEach(field => {
                    if (['itemCd', 'itemClsCd', 'itemTyCd', 'orgnNatCd','qtyUnitCd','taxTyCd','pkgUnitCd'].includes(field)) {
                            return; // Skip to the next iteration
                        }

                    order[field] = paymentResult[field];
                    if (!order[field]) {
                        errorMessages.push(fields[field]);
                    }
                });

                if (errorMessages.length > 0) {
                    Gui.showPopup('ErrorPopup', {
                        title: 'KRA E-TIMS ERROR',
                        body: errorMessages.join('\n')
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

                console.log("===Custom function called successfully:===", signResult);

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
                        sdcId: signResult.sdc_id,
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


                    console.log("===Custom order:===", order);
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
