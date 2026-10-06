import { Plugin } from "@html_editor/plugin";
import { unwrapContents } from "@html_editor/utils/dom";

const FORMAT_SELECTOR = "b, strong, i, em, u, s";

/**
 * Pasted or dropped content loses its inline formatting (bold, italic, ...),
 * like in a textarea. Mentions and links are kept.
 */
export class StripPastedFormatPlugin extends Plugin {
    static id = "stripPastedFormat";
    /** @type {import("plugins").EditorResources} */
    resources = {
        // Paste and drop both end up inserting through the dom plugin.
        before_insert_processors: (container) => {
            for (const el of container.querySelectorAll(FORMAT_SELECTOR)) {
                unwrapContents(el);
            }
            return container;
        },
    };
}
