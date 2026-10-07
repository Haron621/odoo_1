/* global AbaPayway */

import { htmlEscape } from '@odoo/owl';

import { loadJS } from '@web/core/assets';
import { _t } from '@web/core/l10n/translation';
import { patch } from '@web/core/utils/patch';

import { PaymentForm } from '@payment/interactions/payment_form';

const ABA_PAYWAY_BASE_URL = 'https://checkout.payway.com.kh';
const SDK_LOADING_TIMEOUT = 10000; // The maximum time to wait for the SDK to load, in ms

patch(PaymentForm.prototype, {

    // #=== DOM MANIPULATION ===#

    /**
     * Prepare the inline form of ABA PayWay for direct payment.
     *
     * @override method from @payment/interactions/payment_form
     * @private
     * @param {number} providerId - The id of the selected payment option's provider.
     * @param {string} providerCode - The code of the selected payment option's provider.
     * @param {number} paymentOptionId - The id of the selected payment option.
     * @param {string} paymentMethodCode - The code of the selected payment method, if any.
     * @param {string} flow - The online payment flow of the selected payment option.
     * @return {void}
     */
    async _prepareInlineForm(providerId, providerCode, paymentOptionId, paymentMethodCode, flow) {
        if (providerCode !== 'aba_payway') {
            await super._prepareInlineForm(...arguments);
            return;
        }

        // Overwrite the payment flow of the selected payment method
        this._setPaymentFlow('direct');
    },

    // #=== PAYMENT FLOW ===#

    /**
     * Open the ABA PayWay checkout to process the payment.
     *
     * @override method from @payment/interactions/payment_form
     * @private
     * @param {string} providerCode - The code of the selected payment option's provider.
     * @param {number} paymentOptionId - The id of the selected payment option.
     * @param {string} paymentMethodCode - The code of the selected payment method, if any.
     * @param {object} processingValues - The processing values of the transaction.
     * @return {void}
     */
    async _processDirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode !== 'aba_payway') {
            await super._processDirectFlow(...arguments);
            return;
        }

        try {
            await this._loadAbaPaywaySdk();
            AbaPayway.checkout({
                ...this._prepareAbaPaywayOptions(processingValues),
                // The SDK fails to handle the payment result if the callbacks are not defined
                onSuccess: () => {},
                onError: () => {},
            });
        } catch (error) {
            this._displayErrorDialog(_t("Payment processing failed"), error.message);
            this._enableButton(); // The button has been disabled before initiating the flow
        }
    },

    /**
     * Load the ABA PayWay SDK.
     *
     * The `checkout2-0.js` script provided by ABA PayWay is a loader that injects the actual SDK
     * scripts, the one defining the `AbaPayway` global being injected after a one-second delay.
     * The SDK is thus considered loaded once that global is defined.
     *
     * @private
     * @return {Promise<void>}
     */
    async _loadAbaPaywaySdk() {
        // `loadJS` returns the same promise for a given URL, so the loader is executed once
        await this.waitFor(loadJS(`${ABA_PAYWAY_BASE_URL}/plugins/checkout2-0.js`));
        await this.waitFor(new Promise((resolve, reject) => {
            const startTime = Date.now();
            const checkSdkLoaded = () => {
                // The global is declared with `const` and is thus not a property of `window`
                if (typeof AbaPayway !== 'undefined') {
                    resolve();
                } else if (Date.now() - startTime > SDK_LOADING_TIMEOUT) {
                    reject(new Error(_t("The ABA PayWay checkout could not be loaded.")));
                } else {
                    setTimeout(checkSdkLoaded, 100);
                }
            };
            checkSdkLoaded();
        }));
    },

    /**
     * Prepare the options to pass to the ABA PayWay checkout.
     *
     * The SDK builds the request form by interpolating each value in a single-quoted HTML
     * attribute without escaping it. The values are thus HTML-escaped so that special characters
     * (e.g., an apostrophe in the email) are submitted unchanged and the signature remains valid.
     *
     * @private
     * @param {object} processingValues - The processing values of the transaction.
     * @return {object} The checkout options.
     */
    _prepareAbaPaywayOptions(processingValues) {
        const options = {
            'req_time': processingValues['req_time'],
            'merchant_id': processingValues['merchant_id'],
            'tran_id': processingValues['tran_id'],
            'amount': processingValues['amount'],
            'firstname': processingValues['firstname'],
            'lastname': processingValues['lastname'],
            'email': processingValues['email'],
            'phone': processingValues['phone'],
            'type': processingValues['type'],
            'payment_option': processingValues['payment_option'],
            'return_url': processingValues['return_url'],
            'cancel_url': processingValues['cancel_url'],
            'continue_success_url': processingValues['continue_success_url'],
            'currency': processingValues['currency'],
            'lifetime': processingValues['lifetime'],
            'skip_success_page': processingValues['skip_success_page'],
            'payment_gate': processingValues['payment_gate'],
            'form_url': processingValues['form_url'],
            'hash': processingValues['hash'],
        };
        return Object.fromEntries(
            Object.entries(options).map(([key, value]) => [key, String(htmlEscape(value))])
        );
    },

});
