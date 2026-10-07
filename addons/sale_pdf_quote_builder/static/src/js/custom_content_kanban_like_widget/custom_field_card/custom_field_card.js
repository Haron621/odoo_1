<<<<<<< 345baa1d29a9027634fb099463f14b2601b63086
import { Component, useProps, signal, t, useEffect } from "@odoo/owl";
||||||| d1403379ee43b244a8df0e7c3d4ff807ab1d0a96
import { useRef } from "@web/owl2/utils";
import { Component } from "@odoo/owl";
=======
import { useRef } from "@web/owl2/utils";
import { Component, signal, useEffect } from "@odoo/owl";
>>>>>>> 89802eac9be8709aea94e76f39763d996b34b06f
import { _t } from "@web/core/l10n/translation";
import { useAutoresize } from "@web/core/utils/autoresize";

export class CustomFieldCard extends Component {
    static template = "sale_pdf_quote_builder.customFieldCard";
    props = useProps({
        name: t.string(),
        value: t.string(),
        onChange: t.function(),
        readonly: t.boolean().optional(),
    });

    customFormFieldTextAreaRef = signal.ref();

    setup() {
<<<<<<< 345baa1d29a9027634fb099463f14b2601b63086
        this.value = signal(this.props.value || "");
        useEffect(() => this.value.set(this.props.value || ""));
||||||| d1403379ee43b244a8df0e7c3d4ff807ab1d0a96
        this.customFormFieldTextAreaRef = useRef('customFieldCardTextArea');
=======
        this.value = signal(this.props.value || "");
        useEffect(() => this.value.set(this.props.value || ""));
        this.customFormFieldTextAreaRef = useRef('customFieldCardTextArea');
>>>>>>> 89802eac9be8709aea94e76f39763d996b34b06f
        this.placeholder = _t("Click to write content for the PDF quote...");
        useAutoresize(this.customFormFieldTextAreaRef);
    }

    expandTextArea(ev) {
        const textarea = ev.target;
        textarea.style.height = textarea.scrollHeight + "px";
    }
}
