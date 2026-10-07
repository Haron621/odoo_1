import { Component, types, useProps } from "@odoo/owl";

import { useService } from "@web/core/utils/hooks";

export class VoicePlaybackRate extends Component {
    static template = "mail.VoicePlaybackRate";

    setup() {
        super.setup();
        this.playbackRates = [0.75, 1, 1.25, 1.5, 2];
        this.store = useService("mail.store");
        this.props = useProps({
            attachment: types.instanceOf(this.store["ir.attachment"]),
        });
    }

    cyclePlaybackRate() {
        const { voiceMetadata } = this.props.attachment;
        const currentIndex = this.playbackRates.indexOf(voiceMetadata.playbackRate);
        const nextIndex = (currentIndex + 1) % this.playbackRates.length;
        voiceMetadata.playbackRate = this.playbackRates[nextIndex];
    }
}
