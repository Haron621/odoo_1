import { Component, useProps, t, signal }  from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

export const contactActionsRegistry = registry.category("website.team_board_snippet.modal_actions");

export class SendMessageModal extends Component {
    static template = "website.s_team_board.send_message_modal"
    static components = { Dialog }

    props = useProps({
        name: t.string(),
        role: t.string(),
        description: t.string(),
        photo: t.string(),
        email: t.string().optional("mail.placeholder@mail.com"),
    });

    loadingActionId = signal(null);

    get contactActions() {
        return contactActionsRegistry
            .getAll()
            .sort((a, b) => (a.sequence || 100) - (b.sequence || 100));
    }

    setup() {
        this.notification = useService("notification");
    }

    async handleActionClick(contactAction) {
        if (this.loadingActionId()) return;
        this.loadingActionId.set(contactAction.id);
        try {
            await contactAction.action({
                    env: this.env,
                    props: this.props,
                    notification: this.notification,
                });
            this.env.dialogData.close();
        } catch {
        } finally {
            this.loadingActionId.set(null);
        }
    }
}

contactActionsRegistry.add("send_message", {
    id: "send_message",
    label: "Send Message",
    loadingLabel: "Sending...",
    btnClass: "btn-primary",
    sequence: 10,
    action: async ({ notification }) => {
        const shouldFail = Math.random() < 0.5;
        try {
            await new Promise((resolve, reject) => {
                setTimeout(() => (shouldFail ? reject(new Error("Random error")) : resolve()), 1000);
            });
            notification.add(_t("Message sent!"), {
                title: "Success",
                type: "success",
            });
        } catch {
            notification.add(_t("Could not send your message"), {
                title: "Error",
                type: "danger",
                sticky: true,
            });
            throw new Error("unable to send message")
        }
    },
});
