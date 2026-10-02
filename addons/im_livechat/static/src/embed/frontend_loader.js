import { canLoadLivechat } from "@im_livechat/embed/common/misc";
import { loadBundle } from "@web/core/assets";
import { registry } from "@web/core/registry";

/**
 * The services of a lazy loaded bundle are not all started when it
 * is loaded.
 */
export const livechatServicesStarted = Promise.withResolvers();

export async function loadLivechatAssets() {
    await loadBundle("html_editor.assets_editor_frontend");
    await loadBundle("im_livechat.assets_embed_frontend");
    await livechatServicesStarted.promise;
}

export const livechatLoaderService = {
    start() {
        if (canLoadLivechat()) {
            loadLivechatAssets();
        }
    },
};
registry.category("services").add("im_livechat.loader", livechatLoaderService);
