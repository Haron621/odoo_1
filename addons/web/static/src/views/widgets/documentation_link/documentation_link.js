import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { Component, t, useProps, computed } from "@odoo/owl";
import { registry } from "@web/core/registry";

const LINK_REGEX = new RegExp("^https?://");

export class DocumentationLink extends Component {
    static template = "web.DocumentationLink";
    props = useProps({
        ...standardWidgetProps,
        class: t.or([t.string(), t.object()]).optional(),
        record: t.object().optional(), // The record is not needed in this widget
        path: t.string(),
        label: t.string().optional(),
        hideIcon: t.boolean().optional(false),
    });

    label = computed(() =>
        typeof this.props.label === "string" ? this.props.label : "View Documentation"
    );

    get url() {
        if (LINK_REGEX.test(this.props.path)) {
            return this.props.path;
        } else {
            return "/web/documentation/open" + this.props.path;
        }
    }

    get classes() {
        let classes = "o_doc_link";
        if (this.props.class) {
            if (this.props.class instanceof Object) {
                classes = { ...this.props.class, [classes]: true };
            } else {
                classes += " " + this.props.class;
            }
        }
        return classes;
    }
}

export const documentationLink = {
    component: DocumentationLink,
    extractProps: ({ attrs }) => {
        const { path, label, "hide-icon": hideIcon, class: classes } = attrs;
        return {
            path,
            label,
            hideIcon: hideIcon === "True",
            class: classes,
        };
    },
    additionalClasses: ["d-inline"],
};

registry.category("view_widgets").add("documentation_link", documentationLink);
