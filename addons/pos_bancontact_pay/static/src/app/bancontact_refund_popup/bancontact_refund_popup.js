import { Component, computed, signal, useProps, t } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";

export class BancontactRefundPopup extends Component {
    static template = "pos_bancontact_pay.BancontactRefundPopup";
    static components = { Dialog };
    props = useProps({
        payments: t.array(),
        amounts: t.object().optional({}),
        getPayload: t.function(),
        close: t.function(),
    });

    setup() {
        this.pos = usePos();
        this.rows = this.props.payments.map((payment) => {
            const input = signal(this.props.amounts[payment.id] ?? "");
            const amount = computed(() => Number(input()) || 0);
            return {
                payment,
                input,
                amount,
                isTooHigh: computed(() => this.pos.currency.isPositive(amount() - payment.amount)),
            };
        });
        this.totalAmount = this.props.payments.reduce(
            (total, payment) => total + payment.amount,
            0
        );
        this.totalRefund = computed(() =>
            this.rows.reduce((total, row) => total + row.amount(), 0)
        );
        this.canConfirm = computed(() => !this.rows.some((row) => row.isTooHigh()));
    }

    confirm() {
        if (!this.canConfirm()) {
            return;
        }
        this.props.getPayload(
            this.rows.map((row) => ({ payment: row.payment, amount: row.amount() }))
        );
        this.props.close();
    }
}
