import { patch } from "@web/core/utils/patch";
import { PaymentScreenStatus } from "@point_of_sale/app/screens/payment_screen/payment_status/payment_status";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";

patch(PaymentScreenStatus.prototype, {
    async onClickSplitAndPay() {
        const originOrder = this.props.order;
        const paymentLines = originOrder.payment_ids;
        const paidAmount = paymentLines.reduce((sum, line) => sum + line.amount, 0);

        if (paidAmount <= 0) {
            return;
        }

        const splitProduct = this.pos.config.split_payment_product_id;

        const floatingOrder = this.pos.addNewOrder({ floating_order_name: "Split Payment" });
        floatingOrder.split_payment_origin_uuid = originOrder.uuid;

        await this.pos.addLineToOrder(
            {
                product_id: splitProduct,
                product_tmpl_id: splitProduct.product_tmpl_id,
                qty: 1,
                price_unit: paidAmount,
            },
            floatingOrder
        );

        await this.pos.addLineToOrder(
            {
                product_id: splitProduct,
                product_tmpl_id: splitProduct.product_tmpl_id,
                qty: 1,
                price_unit: -paidAmount,
            },
            originOrder
        );

        for (const line of [...paymentLines]) {
            const method = line.payment_method_id;
            const amount = line.amount;

            const result = floatingOrder.addPaymentline(method);

            if (result.status && result.data) {
                result.data.setAmount(amount);
            }

            originOrder.removePaymentline(line);
        }

        this.pos.setOrder(floatingOrder);

        const validationOptions = this.pos.getValidationOrderOptions({ order: floatingOrder });
        const validation = new OrderPaymentValidation(validationOptions);

        return await validation.validateOrder(false);
    },
});
