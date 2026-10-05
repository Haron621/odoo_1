import { registry } from "@web/core/registry";

registry.category("website.team_board_snippet.modal_actions").add("copy_email", {
    id: "copy_email",
    label: "Copy Email",
    loadingLabel: "Copying...",
    btnClass: "btn-outline-secondary",
    sequence: 20,
    action: async ({ props, notification }) => {
        if (props.email) {
            await navigator.clipboard.writeText(props.email);
            notification.add("Email copied to clipboard!", { type: "success" });
        } else {
            notification.add("No email available for this member", { type: "warning" });
        }
    },
});
