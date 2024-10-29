odoo.define('l10n_ke_etims_vscu_pos.ReceiptScreen', function (require) {
    'use strict';

    const Registries = require("point_of_sale.Registries");
    const ReceiptScreen = require("point_of_sale.ReceiptScreen");
    const rpc = require("web.rpc");
    const { Gui } = require('point_of_sale.Gui');

    const ReceiptScreenExtend = ReceiptScreen => class extends ReceiptScreen {

        async handleAutoPrint() {
                if (this._shouldAutoPrint()) {
                    await this.env.pos.get_order();
                    const currentOrder = this.env.pos.get_order();
                    const orderData = currentOrder.export_as_JSON(); // Collect order data to send to the backend

                    console.log('====ordey====', orderData)

                    // Call your custom backend function via rpc before finalizing the order
                    await rpc.query({
                        model: 'pos.order',
                        method: 'sign_order',
                        args: [{}, orderData]  // // Pass empty
                    }).then((result) => {
                        if (result) {

                            currentOrder.pmtTyCd = result.pmtTyCd;
                            // Check if pmtTyCd is empty
                            if (!currentOrder.pmtTyCd) {
                                Gui.showPopup('ErrorPopup', {
                                    title: 'KRA E-TIMS ERROR',
                                    body: 'Payment Type Code is empty..'
                                });
                                throw new Error("Payment Type Code is empty.");
                            }
                            currentOrder.ke_etims_rcpt_sign = result.rcptSign;
                            currentOrder.ke_etims_sdc_date_time = result.ke_etims_sdc_date_time;
                            currentOrder.l10n_ke_qr_code = result.l10n_ke_qr_code
                            currentOrder.branch_seq = result.branch_seq;
                            currentOrder.ke_etims_intrl_data_formatted = result.intrlData;
                            currentOrder.ke_etims_rcpt_sign_formatted = result.ke_etims_rcpt_sign_formatted;
                            currentOrder.tax_mapping = result.tax_mapping;
                            currentOrder.sdc_id = result.sdc_id;
                            currentOrder.rcpt_no = result.rcpt_no;
                            currentOrder.cu_invoice_no = result.cu_invoice_no
                            currentOrder.vsdc_rcpt_date = result.vsdc_rcpt_date
                            currentOrder.vsdc_rcpt_time = result.vsdc_rcpt_time
                            currentOrder.number_of_items = result.number_of_items
                            currentOrder.total_before_discount = result.total_before_discount
                            currentOrder.discount_amount = result.discount_amount
                            currentOrder.taxblAmtA = result.taxblAmtA
                            currentOrder.taxblAmtB = result.taxblAmtB
                            currentOrder.taxblAmtC = result.taxblAmtC
                            currentOrder.taxblAmtD = result.taxblAmtD
                            currentOrder.taxblAmtE = result.taxblAmtE
                            currentOrder.taxAmtA = result.taxAmtA
                            currentOrder.taxAmtB = result.taxAmtB
                            currentOrder.taxAmtC = result.taxAmtC
                            currentOrder.taxAmtD = result.taxAmtD
                            currentOrder.taxAmtE = result.taxAmtE
                        }
                        else{
                            // #pop up error message
                              Gui.showPopup('ErrorPopup', {
                            title: 'KRA E-TIMS ERROR',
                            body: 'There was an issue communicating with the server.',
                        });

                        }
                    }).catch((error) => {
                        // #pop up error message
                        Gui.showPopup('ErrorPopup', {
                            title: 'KRA E-TIMS ERROR',
                            body: 'There was an issue communicating with the server.'
                        });

                    });

                    await this.printReceipt();
                    if (this.currentOrder && this.currentOrder === currentOrder && currentOrder._printed && this._shouldCloseImmediately()) {
                        this.whenClosing();
                    }
                }

            return super.handleAutoPrint();
            }

    }

    Registries.Component.extend(ReceiptScreen, ReceiptScreenExtend);
});
