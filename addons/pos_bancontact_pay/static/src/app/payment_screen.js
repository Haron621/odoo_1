import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { patch } from "@web/core/utils/patch";
import { BancontactRefundPopup } from "@pos_bancontact_pay/app/bancontact_refund_popup/bancontact_refund_popup";

patch(PaymentScreen.prototype, {
    get bancontactPaymentMethod() {
        return this.payment_methods_from_config.find(
            (method) => method.payment_provider === "bancontact_pay"
        );
    },

    get showBancontactRefund() {
        return this.isRefundOrder && Boolean(this.bancontactPaymentMethod);
    },

    get bancontactRefundablePayments() {
        const refundedOrder = this.currentOrder.lines[0]?.refunded_orderline_id?.order_id;
        const payments = refundedOrder?.payment_ids || [];
        return payments.filter(
            (payment) => payment.payment_provider === "bancontact_pay" && payment.isDone()
        );
    },

    /**
     * The refund line of this order linked to the given original payment, if any.
     */
    getBancontactRefundLine(payment) {
        return this.paymentLines.find(
            (line) => line.bancontact_refunded_payment_id?.id === payment.id
        );
    },

    async onClickBancontactRefund() {
        const payments = this.bancontactRefundablePayments;
        if (!payments.length) {
            return;
        }

        let refunds;
        if (payments.length === 1) {
            refunds = [{ payment: payments[0], amount: payments[0].amount }];
        } else {
            const amounts = {};
            for (const payment of payments) {
                const refundLine = this.getBancontactRefundLine(payment);
                if (refundLine) {
                    amounts[payment.id] = Math.abs(refundLine.amount);
                }
            }
            refunds = await makeAwaitable(this.dialog, BancontactRefundPopup, {
                payments,
                amounts,
            });
            if (!refunds) {
                return;
            }
        }

        for (const { payment, amount } of refunds) {
            const refundLine = this.getBancontactRefundLine(payment);
            if (refundLine && amount > 0) {
                refundLine.setAmount(-amount);
            } else if (refundLine) {
                this.currentOrder.removePaymentline(refundLine);
            } else if (amount > 0) {
                const result = this.currentOrder.addPaymentline(payment.payment_method_id);
                if (result.status) {
                    result.data.setAmount(-amount);
                    result.data.bancontact_refunded_payment_id = payment;
                }
            }
        }
        this.numberBuffer.reset();
    },
});
