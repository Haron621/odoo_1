import { DiscussContent } from "@mail/core/public_web/discuss_content";

import { patch } from "@web/core/utils/patch";

patch(DiscussContent.prototype, {
    getPanelContainer(params) {
        if (params.action.id === "create-lead") {
            return this.panelPopover;
        }
        return super.getPanelContainer(params);
    },
});
